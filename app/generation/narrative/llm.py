"""LLM 客户端抽象 + mock 实现 + OpenAI 兼容实现。

核心设计：
  - LLM 只做"选择 + 组装"，不做事实生产；
  - 输出必须是结构化 JSON（{"text": ..., "source_ids": [...]}），
    解析失败即抛异常，由上层降级到人工，不进入报告。

生产接入：设置 LLM_PROVIDER=openai_compatible + LLM_BASE_URL/LLM_API_KEY/LLM_MODEL_ID，
指向私有化部署（vLLM / Qwen 等 OpenAI 兼容接口），数据不出域。
"""

from __future__ import annotations

import json
import time
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

    超时 + 重试 + 结构化输出校验；解析失败即抛异常（由上层降级到人工）。
    """

    model_id: str
    base_url: str
    api_key: str
    timeout: int = 120
    max_retries: int = 2

    def generate(self, prompt: dict[str, Any], response_format: str | None = None) -> dict[str, Any]:
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": self._format_prompt(prompt)}],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                data = self._post(payload)
                return self._parse(data)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(1 * (attempt + 1))
        raise RuntimeError(f"LLM 调用失败（已重试 {self.max_retries} 次）：{last_err}")

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        import urllib.request

        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _parse(data: dict[str, Any]) -> dict[str, Any]:
        content = data["choices"][0]["message"]["content"]
        obj = json.loads(content)
        text = obj.get("text")
        sources = obj.get("source_ids", [])
        if not isinstance(text, str) or not text.strip():
            raise ValueError("LLM 返回缺少有效 text 字段")
        if not isinstance(sources, list):
            sources = []
        return {"text": text, "source_ids": sources}

    @staticmethod
    def _format_prompt(prompt: dict[str, Any]) -> str:
        section_type = prompt["section_type"]
        variables = prompt["variables"]
        candidates = prompt["candidates"]
        cand_lines = "\n".join(f"- [{c['id']}] {c['text']}" for c in candidates) or "（无）"
        return (
            f"你是报告初稿组装助手。请为「{section_type}」章节生成一段叙述文本。\n\n"
            "规则：\n"
            "1. 只能从下方「已批准文本候选」中选择并拼接，禁止编造任何数值或事实；\n"
            "2. 所有数值必须来自「研究变量」，不得篡改；\n"
            '3. 只返回 JSON，格式：{"text": "叙述文本", "source_ids": ["用到的候选id"]}。\n\n'
            f"研究变量：\n{json.dumps(variables, ensure_ascii=False)}\n\n"
            f"已批准文本候选：\n{cand_lines}"
        )


def make_llm_client(cfg: LLMConfig):
    """根据配置构建 LLM 客户端。默认 mock，零外部依赖。"""
    if cfg.provider == "openai_compatible":
        if not cfg.base_url or not cfg.model_id:
            raise ValueError("openai_compatible 模式需要设置 LLM_BASE_URL 和 LLM_MODEL_ID")
        return OpenAICompatibleClient(
            model_id=cfg.model_id, base_url=cfg.base_url, api_key=cfg.api_key
        )
    return MockLLMClient(model_id=cfg.model_id)
