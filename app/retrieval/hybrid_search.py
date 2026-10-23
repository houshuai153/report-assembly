"""混合检索：向量相似度 + 关键词重叠 + 元数据过滤。

根据当前报告的研究元数据（分析物、基质、方法平台、物种），
自动召回最相关的历史文本片段作为候选。
"""

from __future__ import annotations

from typing import Any

from .embed import cosine, embed


class Retriever:
    def __init__(self, corpus: list[dict[str, Any]]) -> None:
        self.corpus = corpus
        self._index = [(doc, embed(doc["text"])) for doc in corpus]

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        qvec = embed(query)
        scored: list[tuple[float, dict[str, Any]]] = []

        for doc, dvec in self._index:
            if not self._match(doc, filters):
                continue
            vec_score = cosine(qvec, dvec)
            kw_score = self._keyword_overlap(query, doc["text"])
            meta_score = 1.0 if doc["section_type"] in query else 0.0
            score = 0.6 * vec_score + 0.3 * kw_score + 0.1 * meta_score
            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    @staticmethod
    def _match(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
        return all(doc.get(k) == v for k, v in filters.items())

    @staticmethod
    def _keyword_overlap(query: str, text: str) -> float:
        a = set(embed(query).keys())
        b = set(embed(text).keys())
        if not a:
            return 0.0
        return len(a & b) / len(a)
