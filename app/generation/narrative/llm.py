"""LLM 客户端抽象 + mock 实现 + 可选 OpenAI 兼容实现。

核心设计：
  - LLM 只做"选择 + 组装"，不做事实生产；
  - 输出必须是结构化 JSON（{"text": ..., "source_ids": [...]}），
    LLM 说了什么与系统接受了什么之间有明确的 schema 边界。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.config import LLMConfig


class MockLLMClient(BaseModel):
    """确定性 mock：从候选中选择 + 用研究变量组装文本。

    输出与真实 LLM 同构，保证 demo 可复现、可测试。
    """

    model_id: str = "mock-llm-1"

    def generate(self, prompt: dict[str, Any], response_format: str | None = None) -> dict[str, Any]:
        section_type = prompt["section_type"]
        variables = prompt["variables"]
        candidates = prompt["candidates"]

        # mock 选择 top-2 候选（真实模型在这里做"检索 + 选择"）
        selected = candidates[:2]
        source_ids = [c["id"] for c in selected]
        text = self._assemble(section_type, variables, selected)
        return {"text": text, "source_ids": source_ids}

    @staticmethod
    def _assemble(section_type: str, variables: dict[str, Any], selected: list[dict]) -> str:
        v = variables
        lines: list[str] = []

        if section_type == "method_description":
            lines.append(
                f"A validated {v['method_platform']} method was used for the "
                f"quantification of {v['analyte']} in {v['matrix']}. "
                f"The lower limit of quantification was {v['lloq']} ng/mL."
            )
        elif section_type == "result_summary":
            lines.append(
                f"Following administration, {v['analyte']} in {v['matrix']} exhibited "
                f"a mean Cmax of {v['mean_cmax']} ng/mL at a median Tmax of "
                f"{v['median_tmax']} h, with a mean terminal half-life of "
                f"{v['mean_t1_2']} h."
            )
        elif section_type == "qc_summary":
            lines.append(
                f"All analytical runs met the predefined acceptance criteria. A total "
                f"of {v['total_samples']} samples were analyzed, of which "
                f"{v['below_loq']} were below the lower limit of quantification."
            )
        else:
            lines.append(f"Section '{section_type}' assembled from approved text.")

        # 追加"已批准文本"候选（LLM 选中的部分）
        for c in selected:
            lines.append(c["text"])

        return "\n\n".join(lines)


class OpenAICompatibleClient(BaseModel):
    """OpenAI 兼容的私有化部署接口（内网合规，数据不出域）。

    使用标准 HTTP + JSON mode，强制结构化输出；解析失败即抛出，
    由上层降级到人工，不进入报告。
    """

    model_id: str
    base_url: str
    api_key: str

    def generate(self, prompt: dict[str, Any], response_format: str | None = None) -> dict[str, Any]:
        import urllib.request

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}
            ],
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


def make_llm_client(cfg: LLMConfig):
    """根据配置构建 LLM 客户端。默认 mock，零外部依赖。"""
    if cfg.provider == "openai_compatible":
        return OpenAICompatibleClient(
            model_id=cfg.model_id, base_url=cfg.base_url, api_key=cfg.api_key
        )
    return MockLLMClient(model_id=cfg.model_id)
