"""PII / PHI 扫描与脱敏：生成文本进报告前做最后一道拦截。

命中敏感信息（身份证号、手机号、邮箱、固定电话等）时：
  - 脱敏：把敏感串替换为 ***
  - 上报：返回命中明细，供调用方写审计（PII_DETECTED）

说明：中文姓名的正则识别不可靠（2~4 个汉字），这里不强行匹配姓名，
生产环境可接入 NER 模型或字典做更完整的识别。
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("id_card", re.compile(r"\b\d{17}[\dXx]\b|\b\d{15}\b")),          # 身份证 18/15 位
    ("mobile", re.compile(r"\b1[3-9]\d{9}\b")),                       # 手机号
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),           # 邮箱
    ("landline", re.compile(r"\b0\d{2,3}-\d{7,8}\b")),                 # 固定电话
    ("id_like", re.compile(r"\b\d{11,19}\b")),                         # 长数字串（兜底）
]


def scan(text: str) -> list[dict]:
    """扫描文本，返回命中明细。"""
    hits: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for ptype, pat in _PATTERNS:
        for m in pat.finditer(text):
            if (m.start(), m.end()) in seen:
                continue
            seen.add((m.start(), m.end()))
            hits.append({
                "type": ptype,
                "value": m.group(),
                "start": m.start(),
                "end": m.end(),
            })
    return sorted(hits, key=lambda h: h["start"])


def redact(text: str) -> tuple[str, list[dict]]:
    """脱敏并返回（脱敏后文本, 命中明细）。"""
    hits = scan(text)
    redacted = text
    # 从后往前替换，避免索引偏移
    for h in sorted(hits, key=lambda h: -h["start"]):
        redacted = redacted[: h["start"]] + "***" + redacted[h["end"]:]
    return redacted, hits
