"""轻量文本向量化：词频向量 + 余弦相似度（demo，零依赖）。

生产环境替换为 embedding 模型 + pgvector，接口保持不变（embed / cosine）。
数据量在 CRO 报告场景下是千到万级文档，pgvector 完全够用。
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def embed(text: str) -> dict[str, float]:
    """归一化的词频向量。"""
    tokens = tokenize(text)
    counts = Counter(tokens)
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    """两个归一化向量的余弦相似度（等价于点积）。"""
    if not v1 or not v2:
        return 0.0
    common = v1.keys() & v2.keys()
    return sum(v1[k] * v2[k] for k in common)
