"""哈希链审计追踪：追加式、可验证、防篡改。

每次生成或修改操作作为一条追加式记录，记录包含操作者身份、工具/模型标识、
输入输出摘要、时间戳和前序哈希。任何对历史记录的篡改都会导致链验证失败。

要点：
  - actor 字段区分人和 AI：AI 生成记录的 actor 是 "AI:model_id"，
    触发者（人）放在 metadata 里，从而回答"谁让 AI 生成了这段内容"。
  - 人工修改不覆盖 AI 生成的记录，而是追加一条 HUMAN_EDIT 记录，
    形成"AI 生成 → 人修改 → 人批准"的完整序列。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def hash_text(s: str) -> str:
    """内容 SHA256，内容变了哈希就变。"""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class AuditEntry(BaseModel):
    """一条追加式审计记录（frozen，防就地篡改）。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_id: str
    timestamp: str
    actor: str                  # 人的 user_id，或 "AI:model_id"
    action: str                 # AI_GENERATE_SECTION / HUMAN_EDIT / APPROVE / ...
    object_type: str            # section / table / report
    object_id: str
    payload_hash: str           # 内容哈希
    previous_hash: str          # 前一条的 hash
    hash: str = ""              # 本条 hash（链指针），append 时补算
    tool: str | None = None     # 触发工具/模型标识
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditChain:
    """追加式哈希链。"""

    def __init__(self, store_path: str | None = None) -> None:
        self._entries: list[AuditEntry] = []
        self.store_path = store_path

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

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
        """追加一条记录，返回本条 hash。"""
        prev = self._entries[-1].hash if self._entries else "GENESIS"
        entry = AuditEntry(
            entry_id=uuid.uuid4().hex,
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=object_id,
            payload_hash=payload_hash,
            previous_hash=prev,
            hash="",
            tool=tool,
            metadata=metadata or {},
        )
        entry = entry.model_copy(update={"hash": self._compute_hash(entry)})
        self._entries.append(entry)
        return entry.hash

    def verify(self) -> tuple[bool, str]:
        """校验整条链完整性。任何篡改都会导致哈希不匹配。"""
        prev = "GENESIS"
        for i, e in enumerate(self._entries):
            if e.previous_hash != prev:
                return False, f"第 {i} 条：previous_hash 不匹配（链断裂）"
            if self._compute_hash(e) != e.hash:
                return False, f"第 {i} 条：内容被篡改（hash 校验失败）"
            prev = e.hash
        return True, "ok"

    def to_jsonl(self) -> str:
        """导出为 JSONL（每行一条记录），便于落盘与审计。"""
        return "\n".join(
            json.dumps(e.model_dump(), ensure_ascii=False) for e in self._entries
        )

    @staticmethod
    def _compute_hash(entry: AuditEntry) -> str:
        """对除 hash 字段外的全部字段做确定性序列化后取 SHA256。"""
        data = entry.model_dump(exclude={"hash"})
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()
