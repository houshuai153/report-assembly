"""端到端 demo：四层架构闭环 + 审计链 + 状态机。

运行：
    python demo_run.py

演示内容：
  1. 源数据治理：CSV(LIMS) 接入 → 校验 → 锁定 → GovernedDataset
  2. 确定性计算：PK 参数 / 质控统计 / 表格（纯函数，零 LLM）
  3. 知识与检索：从已批准文本语料库召回候选
  4. 受控叙述生成：mock LLM 从候选中"选择 + 组装"
  5. 文档组装：合并为报告初稿（AI_DRAFTED）
  6. 状态机：证明 AI 不能直接批准，必须经过人工审核
  7. 人工审核：逐段接受 / 修改，每个动作写审计链
  8. 审计链：完整性校验 + 篡改检测
"""

from __future__ import annotations

import os
import sys

# Windows 控制台默认 GBK，重配为 UTF-8 以正确输出中文与符号
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# 保证从任意目录运行都能 import app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.compliance.audit_chain import AuditChain
from app.compliance.rbac import Role, User
from app.compliance.review_workflow import ReviewWorkflow
from app.config import Config
from app.generation.assembler import Assembler
from app.generation.deterministic import compute
from app.generation.narrative.llm import make_llm_client
from app.generation.narrative.orchestrator import SectionOrchestrator
from app.generation.state_machine import IllegalTransitionError, ReportState
from app.governance.service import GovernanceService
from app.retrieval.corpus import build_corpus
from app.retrieval.hybrid_search import Retriever

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# 参与方（人）
analyst = User(id="u-analyst", name="分析师", roles=frozenset({Role.ANALYST}))
reviewer = User(id="u-reviewer", name="审核员", roles=frozenset({Role.REVIEWER}))
qa = User(id="u-qa", name="QA 负责人", roles=frozenset({Role.QA_APPROVER}))

SECTION_TITLES = {
    "method_description": "方法描述",
    "result_summary": "结果摘要",
    "qc_summary": "质控总结",
}


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> None:
    cfg = Config.from_env()
    audit = AuditChain(store_path=cfg.audit_store or None)

    # ---------------------------------------------------------------
    banner("第 1 层 · 源数据治理：接入 → 校验 → 锁定")
    # ---------------------------------------------------------------
    metadata = {
        "study_id": "STY-2024-001",
        "analyte": "Compound-X",
        "matrix": "plasma",
        "species": "human",
        "method_platform": "LC-MS/MS",
        "report_type": "clinical_bioanalysis",
    }
    csv_path = os.path.join(DATA_DIR, "sample_concentrations.csv")

    governance = GovernanceService()
    dataset = governance.ingest(csv_path, metadata)
    audit.append(
        action="DATA_LOCKED",
        actor=analyst.id,
        object_type="dataset",
        object_id=dataset.data_version,
        payload_hash="",
        metadata={"study_id": dataset.metadata.study_id, "status": dataset.status.value},
    )
    print(f"✅ 已锁定治理数据对象：{dataset.data_version}")
    print(f"   状态={dataset.status.value}  样本数={len(dataset.concentrations)}")

    # ---------------------------------------------------------------
    banner("第 3 层(确定性) · PK 参数 / 质控统计 / 表格 —— 纯函数，不经过 LLM")
    # ---------------------------------------------------------------
    computed = compute(dataset, loq=cfg.loq, terminal_points=cfg.terminal_points)
    print(computed.tables["pk"])
    print("\n" + computed.tables["qc"])

    # ---------------------------------------------------------------
    banner("第 2 层 · 知识与检索：召回已批准文本候选")
    # ---------------------------------------------------------------
    retriever = Retriever(build_corpus())

    # ---------------------------------------------------------------
    banner("第 3 层(叙述) · 受控生成：mock LLM 只做「选择 + 组装」")
    # ---------------------------------------------------------------
    llm = make_llm_client(cfg.llm)
    orchestrator = SectionOrchestrator(retriever, llm, audit)
    print(f"LLM 客户端：{type(llm).__name__}（model_id={llm.model_id}）")

    sections = {}
    for section_type in ("method_description", "result_summary", "qc_summary"):
        draft = orchestrator.generate_section(section_type, dataset, computed, analyst.id)
        sections[section_type] = draft
        print(f"\n◆ {SECTION_TITLES[section_type]}")
        print(f"  溯源来源：{draft.selected_sources}")
        print(f"  模型版本：{draft.model_version}")
        print(f"  文本预览：{draft.text.splitlines()[0][:80]}...")

    # ---------------------------------------------------------------
    banner("文档组装 → 报告初稿（AI_DRAFTED）")
    # ---------------------------------------------------------------
    assembler = Assembler()
    report = assembler.assemble(dataset, computed, sections)
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, "draft_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report.markdown)
    print(f"✅ 初稿已生成：{out_path}")
    print(f"   当前状态：{report.state.value}")

    # ---------------------------------------------------------------
    banner("状态机：AI 不能自己批准报告")
    # ---------------------------------------------------------------
    print("尝试 AI_DRAFTED -> APPROVED（绕过审核）：")
    try:
        report.transition(ReportState.APPROVED, actor=analyst, audit=audit)
        print("  ⚠️ 竟然成功了（bug）")
    except IllegalTransitionError as e:
        print(f"  ❌ 已拦截：{e}")

    print("\n尝试 AI_DRAFTED -> UNDER_REVIEW（跳过审核队列）：")
    try:
        report.transition(ReportState.UNDER_REVIEW, actor=analyst, audit=audit)
        print("  ⚠️ 竟然成功了（bug）")
    except IllegalTransitionError as e:
        print(f"  ❌ 已拦截：{e}")

    print("\n合法路径 AI_DRAFTED -> PENDING_REVIEW：")
    report.transition(ReportState.PENDING_REVIEW, actor=analyst, audit=audit)
    print(f"  ✅ 当前状态：{report.state.value}")

    # ---------------------------------------------------------------
    banner("第 4 层 · 人工审核：逐段接受 / 修改（每个动作写审计链）")
    # ---------------------------------------------------------------
    workflow = ReviewWorkflow(audit)
    workflow.claim(report, reviewer)  # PENDING_REVIEW -> UNDER_REVIEW
    print(f"审核员已认领 → 状态 {report.state.value}")

    workflow.accept_section(report, reviewer, "method_description")
    print("  ✅ 接受「方法描述」")

    # 审核员发现结果摘要里一个数值需要修正，直接编辑（追加 HUMAN_EDIT，不覆盖 AI 记录）
    workflow.edit_section(
        report, reviewer, "result_summary",
        report.sections["result_summary"].text.replace("median Tmax", "mean Tmax"),
    )
    print("  ✏️  修改「结果摘要」（追加 HUMAN_EDIT 记录）")

    workflow.accept_section(report, reviewer, "qc_summary")
    print("  ✅ 接受「质控总结」")

    print("\n尝试由审核员（非 QA）批准：")
    try:
        workflow.approve(report, reviewer)
        print("  ⚠️ 竟然成功了（bug）")
    except PermissionError as e:
        print(f"  ❌ 已拦截：{e}")

    print("\n由 QA 负责人批准放行：")
    workflow.approve(report, qa)
    print(f"  ✅ 当前状态：{report.state.value}（唯一可放行状态）")

    # ---------------------------------------------------------------
    banner("审计链：完整性校验 + 篡改检测")
    # ---------------------------------------------------------------
    ok, msg = audit.verify()
    print(f"完整链校验：{'✅ 通过' if ok else '❌ ' + msg}（共 {len(audit.entries)} 条记录）")

    print("\n篡改演示：把第 3 条记录的 payload_hash 改成全 0：")
    entries = audit.entries
    tampered = entries[2].model_copy(update={"payload_hash": "0" * 64})
    tampered_chain = AuditChain()
    tampered_chain._entries = entries[:2] + [tampered] + entries[3:]  # noqa: SLF001 模拟攻击者改存储
    ok, msg = tampered_chain.verify()
    print(f"  {'❌ 已检测到：' + msg if not ok else '⚠️ 未检测到（bug）'}")

    # ---------------------------------------------------------------
    banner("审计链摘要")
    # ---------------------------------------------------------------
    for i, e in enumerate(audit.entries):
        tool = f" [tool={e.tool}]" if e.tool else ""
        print(f"{i:2d}. {e.action:24s} actor={e.actor:12s} obj={e.object_type}/{e.object_id[:20]}{tool}")

    print("\n" + "=" * 72)
    print("✅ Demo 完成。四层架构闭环：数据治理 → 确定性计算 → 受控生成 → 合规锚定")
    print("=" * 72)


if __name__ == "__main__":
    main()
