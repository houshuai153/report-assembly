"""最终文档组装：确定性表格 + LLM 叙述合并为报告初稿。

状态机：组装完成后报告处于 AI_DRAFTED，只能进入 PENDING_REVIEW（强制人工审核）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .narrative.orchestrator import SectionDraft
from .state_machine import ReportState, transition


class Report(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    report_id: str
    study_id: str
    state: ReportState = ReportState.INITIALIZED
    sections: dict[str, SectionDraft] = Field(default_factory=dict)
    markdown: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def transition(self, target: ReportState, actor=None, audit=None) -> None:
        self.state = transition(self.state, target, actor=actor, audit=audit, report_id=self.report_id)


class Assembler:
    def assemble(
        self,
        dataset,
        computed,
        sections: dict[str, SectionDraft],
        report_id: str | None = None,
    ) -> Report:
        meta = dataset.metadata
        report = Report(
            report_id=report_id or uuid4().hex,
            study_id=meta.study_id,
            state=ReportState.AI_DRAFTED,
            sections=sections,
            markdown=self._render(dataset, computed, sections),
        )
        return report

    @staticmethod
    def _render(dataset, computed, sections: dict[str, SectionDraft]) -> str:
        meta = dataset.metadata
        md: list[str] = []

        md.append(f"# {meta.report_type} — Draft Report")
        md.append("")
        md.append(f"> **Status:** AI_DRAFTED (pending human review) · "
                  f"**Data version:** {dataset.data_version}")
        md.append("")

        md.append("## Study Metadata")
        md.append("")
        md.append("| Field | Value |")
        md.append("| --- | --- |")
        for k, v in [
            ("Study ID", meta.study_id),
            ("Analyte", meta.analyte),
            ("Matrix", meta.matrix),
            ("Species", meta.species),
            ("Method platform", meta.method_platform),
        ]:
            md.append(f"| {k} | {v} |")
        md.append("")

        md.append("## PK Parameters (deterministic)")
        md.append("")
        md.append(computed.tables["pk"])
        md.append("")

        md.append("## QC Summary (deterministic)")
        md.append("")
        md.append(computed.tables["qc"])
        md.append("")

        section_titles = {
            "method_description": "Method Description",
            "result_summary": "Results Summary",
            "qc_summary": "QC Summary",
        }
        for key, title in section_titles.items():
            if key in sections:
                md.append(f"## {title}")
                md.append("")
                md.append(sections[key].text)
                md.append("")

        return "\n".join(md)
