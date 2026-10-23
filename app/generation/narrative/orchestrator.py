"""章节级编排：检索候选 → 受控 prompt → LLM 生成 → 审计。

审核者看到的不只是"一段文本"，而是"这段文本基于哪些已批准片段、
由哪个模型版本生成"——生成溯源是必查项。
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict

from app.compliance.audit_chain import AuditChain
from app.governance.contracts import GovernedDataset
from app.retrieval.hybrid_search import Retriever
from .llm import MockLLMClient, OpenAICompatibleClient
from .prompt_builder import build_constrained_prompt


class SectionDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    section_type: str
    text: str
    selected_sources: list[str]       # LLM 选了哪些候选
    model_version: str
    input_data_version: str
    generated_at: datetime
    generated_by: str                 # "AI:model_id"
    status: str = "pending_review"


LLMClient = MockLLMClient | OpenAICompatibleClient


class SectionOrchestrator:
    def __init__(self, retriever: Retriever, llm_client: LLMClient, audit: AuditChain) -> None:
        self.retriever = retriever
        self.llm_client = llm_client
        self.audit = audit

    def generate_section(
        self,
        section_type: str,
        dataset: GovernedDataset,
        computed,
        user_id: str,
    ) -> SectionDraft:
        meta = dataset.metadata
        query = f"{section_type} {meta.matrix} {meta.method_platform} {meta.analyte}"

        # 1. 检索候选文本片段（元数据过滤 + 混合打分）
        candidates = self.retriever.search(
            query,
            filters={
                "matrix": meta.matrix,
                "platform": meta.method_platform,
                "report_type": meta.report_type,
            },
            top_k=5,
        )
        candidates = [c for c in candidates if c["section_type"] == section_type]

        # 2. 受控 prompt：LLM 只能选择 + 拼接
        variables = self._variables(dataset, computed, section_type)
        prompt = build_constrained_prompt(section_type, candidates, variables)

        # 3. 调用 LLM，强制结构化输出
        response = self.llm_client.generate(prompt, response_format="json_object")

        # 4. 生成溯源记录
        draft = SectionDraft(
            section_type=section_type,
            text=response["text"],
            selected_sources=response["source_ids"],
            model_version=self.llm_client.model_id,
            input_data_version=dataset.data_version,
            generated_at=datetime.now(timezone.utc),
            generated_by=f"AI:{self.llm_client.model_id}",
            status="pending_review",
        )

        # 5. 写审计链：记录"AI 生成"动作（触发者是人，放在 metadata 里）
        self.audit.append(
            action="AI_GENERATE_SECTION",
            actor=user_id,
            tool=f"LLM:{self.llm_client.model_id}",
            object_type="section",
            object_id=section_type,
            payload_hash=self.audit.hash_text(draft.text),
            metadata={
                "section": section_type,
                "sources": response["source_ids"],
                "data_version": dataset.data_version,
            },
        )

        return draft

    @staticmethod
    def _variables(dataset: GovernedDataset, computed, section_type: str) -> dict:
        meta = dataset.metadata
        qc = computed.qc_summary
        base = {
            "analyte": meta.analyte,
            "matrix": meta.matrix,
            "species": meta.species,
            "method_platform": meta.method_platform,
            "report_type": meta.report_type,
            "lloq": qc.get("lloq", 1.0),
            "total_samples": qc.get("total_samples"),
            "below_loq": qc.get("below_loq"),
            "subjects": qc.get("subjects"),
        }

        if section_type == "result_summary":
            cmaxs = [p["Cmax"] for p in computed.pk_by_subject.values() if p.get("Cmax") is not None]
            tmaxs = [p["Tmax"] for p in computed.pk_by_subject.values() if p.get("Tmax") is not None]
            halves = [p["T1_2"] for p in computed.pk_by_subject.values() if p.get("T1_2") is not None]
            base["mean_cmax"] = round(sum(cmaxs) / len(cmaxs), 3) if cmaxs else None
            base["median_tmax"] = round(sorted(tmaxs)[len(tmaxs) // 2], 3) if tmaxs else None
            base["mean_t1_2"] = round(sum(halves) / len(halves), 3) if halves else None

        return base
