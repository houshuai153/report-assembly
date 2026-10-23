"""PostgreSQL 持久化：报告 + 章节 + 哈希链审计。

哈希链审计沿用 app.compliance.audit_chain.AuditChain 的哈希算法，
只是把"内存 list"换成 audit_entries 表。同一报告的追加通过 advisory lock 串行化
（对应"按 report 维度分区串行化"的合规/并发权衡）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.compliance.audit_chain import AuditChain, AuditEntry, hash_text
from .db import session_scope
from .models import AuditEntryRow, ReportRow


# ---------------- 报告 ----------------

def insert_report(report_id: str, study_id: str, state: str, meta: dict) -> None:
    """先插入占位行（computed/sections/markdown 为空），保证审计外键可用。"""
    with session_scope() as s:
        s.add(ReportRow(
            report_id=report_id, study_id=study_id, state=state,
            meta=meta, computed={}, sections={}, markdown="",
        ))


def finalize_report(report_id: str, state: str, computed: dict, sections: dict, markdown: str) -> None:
    """流水线跑完后，回填最终状态、计算结果、章节与初稿。"""
    with session_scope() as s:
        row = s.get(ReportRow, report_id)
        if row is None:
            raise KeyError(report_id)
        row.state = state
        row.computed = computed
        row.sections = sections
        row.markdown = markdown


def list_reports() -> list[dict[str, Any]]:
    with session_scope() as s:
        rows = s.query(ReportRow).order_by(ReportRow.created_at.desc()).all()
        return [{"report_id": r.report_id, "study_id": r.study_id, "state": r.state} for r in rows]


def get_report(report_id: str) -> dict[str, Any] | None:
    with session_scope() as s:
        row = s.get(ReportRow, report_id)
        if row is None:
            return None
        return {
            "report_id": row.report_id,
            "study_id": row.study_id,
            "state": row.state,
            "metadata": row.meta,
            "pk_by_subject": row.computed.get("pk_by_subject", {}),
            "qc_summary": row.computed.get("qc_summary", {}),
            "sections": row.sections,
            "markdown": row.markdown,
        }


def update_report_state(report_id: str, state: str) -> None:
    with session_scope() as s:
        row = s.get(ReportRow, report_id)
        if row is not None:
            row.state = state


def update_section(report_id: str, section_type: str, new_text: str, status: str) -> None:
    with session_scope() as s:
        row = s.get(ReportRow, report_id)
        if row is None or section_type not in row.sections:
            raise KeyError(section_type)
        new_sections = dict(row.sections)
        sec = dict(new_sections[section_type])
        sec["text"] = new_text
        sec["status"] = status
        new_sections[section_type] = sec
        row.sections = new_sections  # 整体赋值以触发 JSONB 变更检测


# ---------------- 审计链 ----------------

class SqlAuditChain:
    """与内存 AuditChain 同接口，但持久化到 audit_entries 表。"""

    def __init__(self, report_id: str) -> None:
        self.report_id = report_id

    @staticmethod
    def hash_text(s: str) -> str:
        return hash_text(s)

    def append(
        self,
        action: str,
        actor: str,
        object_type: str,
        object_id: str,
        payload_hash: str,
        metadata: dict[str, Any] | None = None,
        tool: str | None = None,
    ) -> str:
        with session_scope() as s:
            # 串行化同一报告的审计写入（advisory lock，事务结束自动释放）
            s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:rid))"), {"rid": self.report_id})
            last = (
                s.query(AuditEntryRow)
                .filter(AuditEntryRow.report_id == self.report_id)
                .order_by(AuditEntryRow.id.desc())
                .first()
            )
            prev = last.hash if last else "GENESIS"

            entry = AuditEntry(
                entry_id=uuid.uuid4().hex,
                timestamp=datetime.now(timezone.utc).isoformat(),
                actor=actor, action=action, object_type=object_type,
                object_id=object_id, payload_hash=payload_hash,
                previous_hash=prev, hash="", tool=tool, metadata=metadata or {},
            )
            entry = entry.model_copy(update={"hash": AuditChain._compute_hash(entry)})

            s.add(AuditEntryRow(
                report_id=self.report_id,
                entry_id=entry.entry_id,
                timestamp=entry.timestamp,
                actor=entry.actor,
                action=entry.action,
                object_type=entry.object_type,
                object_id=entry.object_id,
                payload_hash=entry.payload_hash,
                previous_hash=entry.previous_hash,
                hash=entry.hash,
                tool=entry.tool,
                meta=entry.metadata,
            ))
            return entry.hash

    @property
    def entries(self) -> list[AuditEntry]:
        with session_scope() as s:
            rows = (
                s.query(AuditEntryRow)
                .filter(AuditEntryRow.report_id == self.report_id)
                .order_by(AuditEntryRow.id.asc())
                .all()
            )
            return [self._row_to_entry(r) for r in rows]

    def verify(self) -> tuple[bool, str]:
        entries = self.entries
        prev = "GENESIS"
        for i, e in enumerate(entries):
            if e.previous_hash != prev:
                return False, f"第 {i} 条：previous_hash 不匹配（链断裂）"
            if AuditChain._compute_hash(e) != e.hash:
                return False, f"第 {i} 条：内容被篡改（hash 校验失败）"
            prev = e.hash
        return True, "ok"

    @staticmethod
    def _row_to_entry(row: AuditEntryRow) -> AuditEntry:
        return AuditEntry(
            entry_id=row.entry_id, timestamp=row.timestamp, actor=row.actor,
            action=row.action, object_type=row.object_type, object_id=row.object_id,
            payload_hash=row.payload_hash, previous_hash=row.previous_hash,
            hash=row.hash, tool=row.tool, metadata=row.meta,
        )
