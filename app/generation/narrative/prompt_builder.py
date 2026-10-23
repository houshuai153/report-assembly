"""受控 prompt 组装。

关键约束：LLM 只能从候选中选择 + 拼接，不能自由生成事实。
因此 prompt 是结构化对象，把候选片段和研究特异性变量显式地分开传入。
"""

from __future__ import annotations

from typing import Any


def build_constrained_prompt(
    section_type: str,
    candidates: list[dict[str, Any]],
    variables: dict[str, Any],
) -> dict[str, Any]:
    return {
        "section_type": section_type,
        "instruction": (
            "只从提供的候选文本中选择并拼接，禁止编造任何数值或事实；"
            "数值必须来自 variables 字段。"
        ),
        "variables": variables,
        "candidates": [
            {"id": c["id"], "text": c["text"]} for c in candidates
        ],
    }
