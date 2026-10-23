"""受试者标识伪名化：真实身份 → 稳定假名。

真实 LIMS 里 subject_id 背后可能是姓名 / 病历号 / 身份证。治理层在锁定前
应做伪名化，报告层永远只拿假名。映射用 HMAC 单向生成，稳定且不可逆
（不保存真实身份 → 假名的映射表，避免映射表本身成为泄密点）。
"""

from __future__ import annotations

import hashlib
import hmac
import os


class Pseudonymizer:
    def __init__(self, secret: str | None = None) -> None:
        self.secret = secret or os.environ.get("APP_SECRET", "change-me-in-prod")

    def pseudonymize(self, identifier: str) -> str:
        """真实标识 → 稳定假名（S + HMAC 前 8 位大写）。"""
        digest = hmac.new(
            self.secret.encode("utf-8"), identifier.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return "S" + digest[:8].upper()

    def map_many(self, identifiers: list[str]) -> dict[str, str]:
        """批量伪名化，返回 {真实标识: 假名}。"""
        return {i: self.pseudonymize(i) for i in identifiers}
