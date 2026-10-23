"""审核工作台：FastAPI 后端 + 单页前端（生产版：PostgreSQL 持久化 + 鉴权）。

把四层流水线真正接进 Web：
  登录 → 提交研究 → 治理 → 确定性计算 → 检索 → 受控生成 → 组装 →
  人工审核 → 哈希链审计（全部持久化到 PostgreSQL）

运行（本地，需 PostgreSQL）：
    docker compose up --build
    浏览器打开 http://localhost:8000

环境变量：
    DATABASE_URL   PostgreSQL 连接串（默认指向 docker-compose 的 db）
    APP_PASSWORD   登录密码（默认 demo）
    APP_SECRET     会话签名密钥（生产务必改为强随机值）
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.compliance.audit_chain import AuditEntry
from app.compliance.rbac import Role, User
from app.config import Config
from app.export.service import export_report
from app.generation.assembler import Assembler
from app.generation.deterministic import compute
from app.generation.narrative.llm import make_llm_client
from app.generation.narrative.orchestrator import SectionOrchestrator
from app.generation.state_machine import IllegalTransitionError, ReportState, transition
from app.governance.service import GovernanceError, GovernanceService
from app.retrieval.corpus import build_corpus
from app.retrieval.hybrid_search import Retriever
from app.storage.db import init_db
from app.storage.repository import (
    SqlAuditChain,
    finalize_report,
    get_report,
    insert_report,
    list_reports,
    update_report_state,
    update_section,
)
from .auth import MAX_AGE_SECONDS, check_password, make_token, verify_token

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(PROJECT_ROOT, "data", "sample_concentrations.csv")

# 参与方（人）
ANALYST = User(id="u-analyst", name="分析师", roles=frozenset({Role.ANALYST}))
REVIEWER = User(id="u-reviewer", name="审核员", roles=frozenset({Role.REVIEWER}))
QA = User(id="u-qa", name="QA 负责人", roles=frozenset({Role.QA_APPROVER}))

SECTION_TITLES = {
    "method_description": "方法描述",
    "result_summary": "结果摘要",
    "qc_summary": "质控总结",
}

DEFAULT_METADATA = {
    "study_id": "STY-2024-001",
    "analyte": "Compound-X",
    "matrix": "plasma",
    "species": "human",
    "method_platform": "LC-MS/MS",
    "report_type": "clinical_bioanalysis",
}


class EditBody(BaseModel):
    text: str


class RejectBody(BaseModel):
    reason: str = ""


class LoginBody(BaseModel):
    password: str


def require_auth(session: str | None = Cookie(default=None)) -> bool:
    if not session or not verify_token(session):
        raise HTTPException(status_code=401, detail="unauthorized")
    return True


def _serialize_sections(sections: dict) -> dict[str, Any]:
    return {
        k: {
            "title": SECTION_TITLES[k],
            "text": v.text,
            "status": v.status,
            "selected_sources": v.selected_sources,
            "model_version": v.model_version,
            "input_data_version": v.input_data_version,
        }
        for k, v in sections.items()
    }


def _entry_to_dict(e: AuditEntry) -> dict[str, Any]:
    return {
        "action": e.action,
        "actor": e.actor,
        "object_type": e.object_type,
        "object_id": e.object_id,
        "tool": e.tool,
        "timestamp": e.timestamp,
        "hash": e.hash[:16] + "…",
        "metadata": e.metadata,
    }


def create_app() -> FastAPI:
    init_db()  # 建表（连接失败则明确报错）
    cfg = Config.from_env()
    retriever = Retriever(build_corpus())
    llm = make_llm_client(cfg.llm)
    governance = GovernanceService()
    assembler = Assembler()

    app = FastAPI(title="报告初稿自动组装 · 审核工作台")
    protected = APIRouter(dependencies=[Depends(require_auth)])

    def _get_or_404(report_id: str) -> dict[str, Any]:
        row = get_report(report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="report not found")
        return row

    # ---------------- 公开 ----------------
    @app.post("/login")
    def login(body: LoginBody, response: Response):
        if not check_password(body.password):
            raise HTTPException(status_code=401, detail="密码错误")
        response.set_cookie(
            "session", make_token(), httponly=True, samesite="lax", max_age=MAX_AGE_SECONDS
        )
        return {"ok": True}

    # ---------------- 生成（受保护） ----------------
    @protected.post("/reports")
    def create_report():
        report_id = uuid4().hex
        insert_report(report_id, DEFAULT_METADATA["study_id"], ReportState.INITIALIZED.value, dict(DEFAULT_METADATA))
        audit = SqlAuditChain(report_id)

        try:
            dataset = governance.ingest(CSV_PATH, dict(DEFAULT_METADATA))
        except GovernanceError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        audit.append(
            action="DATA_LOCKED", actor=ANALYST.id, object_type="dataset",
            object_id=dataset.data_version, payload_hash="",
            metadata={"study_id": dataset.metadata.study_id, "status": dataset.status.value},
        )

        computed = compute(dataset, loq=cfg.loq, terminal_points=cfg.terminal_points)
        orchestrator = SectionOrchestrator(retriever, llm, audit)
        sections = {
            t: orchestrator.generate_section(t, dataset, computed, ANALYST.id)
            for t in SECTION_TITLES
        }

        report = assembler.assemble(dataset, computed, sections, report_id=report_id)
        # 初稿完成后强制进入待审队列（AI 不能直接批准）
        report.transition(ReportState.PENDING_REVIEW, actor=ANALYST, audit=audit)

        finalize_report(
            report_id,
            report.state.value,
            {"pk_by_subject": computed.pk_by_subject, "qc_summary": computed.qc_summary},
            _serialize_sections(sections),
            report.markdown,
        )
        return {"report_id": report_id, "study_id": dataset.metadata.study_id, "state": report.state.value}

    # ---------------- 查询（受保护） ----------------
    @protected.get("/reports")
    def list_all_reports():
        return list_reports()

    @protected.get("/reports/{report_id}")
    def get_one_report(report_id: str):
        return _get_or_404(report_id)

    @protected.get("/reports/{report_id}/export")
    def export_document(report_id: str, format: str = "docx"):
        report = _get_or_404(report_id)
        try:
            data, mime = export_report(report, format)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        ext = format.lower() if format.lower() in ("docx", "pdf") else "docx"
        return Response(
            content=data,
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{report["study_id"]}.{ext}"'},
        )

    # ---------------- 审核动作（受保护） ----------------
    @protected.post("/reports/{report_id}/claim")
    def claim(report_id: str):
        row = _get_or_404(report_id)
        state = ReportState(row["state"])
        audit = SqlAuditChain(report_id)
        try:
            new_state = transition(state, ReportState.UNDER_REVIEW, actor=REVIEWER, audit=audit, report_id=report_id)
        except (IllegalTransitionError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        update_report_state(report_id, new_state.value)
        return {"state": new_state.value}

    @protected.post("/reports/{report_id}/sections/{section}/accept")
    def accept_section(report_id: str, section: str):
        row = _get_or_404(report_id)
        if section not in row["sections"]:
            raise HTTPException(status_code=404, detail="section not found")
        audit = SqlAuditChain(report_id)
        text = row["sections"][section]["text"]
        audit.append(
            action="HUMAN_ACCEPT", actor=REVIEWER.id, object_type="section", object_id=section,
            payload_hash=audit.hash_text(text), metadata={"section": section, "decision": "accept"},
        )
        return {"ok": True}

    @protected.post("/reports/{report_id}/sections/{section}/edit")
    def edit_section(report_id: str, section: str, body: EditBody):
        row = _get_or_404(report_id)
        if section not in row["sections"]:
            raise HTTPException(status_code=404, detail="section not found")
        audit = SqlAuditChain(report_id)
        old_text = row["sections"][section]["text"]
        update_section(report_id, section, body.text, "edited")
        audit.append(
            action="HUMAN_EDIT", actor=REVIEWER.id, object_type="section", object_id=section,
            payload_hash=audit.hash_text(body.text),
            metadata={"section": section, "previous_hash": audit.hash_text(old_text)},
        )
        return {"ok": True}

    @protected.post("/reports/{report_id}/sections/{section}/reject")
    def reject_section(report_id: str, section: str, body: RejectBody):
        row = _get_or_404(report_id)
        if section not in row["sections"]:
            raise HTTPException(status_code=404, detail="section not found")
        audit = SqlAuditChain(report_id)
        text = row["sections"][section]["text"]
        audit.append(
            action="HUMAN_REJECT", actor=REVIEWER.id, object_type="section", object_id=section,
            payload_hash=audit.hash_text(text), metadata={"section": section, "reason": body.reason},
        )
        return {"ok": True}

    @protected.post("/reports/{report_id}/approve")
    def approve(report_id: str):
        row = _get_or_404(report_id)
        state = ReportState(row["state"])
        audit = SqlAuditChain(report_id)
        try:
            new_state = transition(state, ReportState.APPROVED, actor=QA, audit=audit, report_id=report_id)
        except (IllegalTransitionError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        update_report_state(report_id, new_state.value)
        return {"state": new_state.value}

    # ---------------- 审计链（受保护） ----------------
    @protected.get("/reports/{report_id}/audit")
    def report_audit(report_id: str):
        _get_or_404(report_id)
        audit = SqlAuditChain(report_id)
        return [_entry_to_dict(e) for e in audit.entries]

    @protected.get("/reports/{report_id}/audit/verify")
    def verify_audit(report_id: str):
        _get_or_404(report_id)
        audit = SqlAuditChain(report_id)
        ok, msg = audit.verify()
        return {"ok": ok, "message": msg, "count": len(audit.entries)}

    app.include_router(protected)

    # ---------------- 前端 ----------------
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    return app


app = create_app()
