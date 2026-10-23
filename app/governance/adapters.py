"""数据接入适配器：把异构源（LIMS / Excel / 仪器工作站）统一成原始记录。

demo 用 CSV 模拟 Watson LIMS 的导出；真实场景每个适配器对接一个源系统，
输出统一为原始记录（dict），再由 validators 校验并转换为强类型契约。
"""

from __future__ import annotations

import csv
from typing import Any

BLQ_MARKERS = {"", "blq", "na", "null", "bql", "<lloq"}


def _parse_concentration(raw: str) -> float | None:
    """把原始浓度字段解析为 float，BLQ 记作 None。"""
    value = raw.strip()
    if value.lower() in BLQ_MARKERS:
        return None
    return float(value)


class LimsAdapter:
    """模拟 Watson LIMS 导出适配器（CSV）。"""

    def read(self, path: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append({
                    "sample_id": r["sample_id"].strip(),
                    "subject_id": r["subject_id"].strip(),
                    "timepoint": float(r["timepoint"]),
                    "concentration": _parse_concentration(r.get("concentration", "")),
                    "run_id": r["run_id"].strip(),
                })
        return rows


class InlineAdapter:
    """从内存 list[dict] 直接接入（demo / 测试用）。"""

    def read(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**r} for r in rows]
