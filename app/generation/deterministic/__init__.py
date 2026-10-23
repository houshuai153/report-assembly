"""确定性计算：纯函数、零 LLM、可单元测试、可复现。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .pk_calculator import calculate_pk_params
from .qc_stats import calculate_qc_summary
from .table_builder import build_pk_table, build_qc_table


class ComputedResults(BaseModel):
    """确定性层的输出：已算好的 PK 参数、质控统计与渲染好的表格。"""

    model_config = ConfigDict(frozen=True)

    pk_by_subject: dict[str, dict[str, float | None]]
    qc_summary: dict[str, Any]
    tables: dict[str, str]


def compute(dataset, loq: float = 1.0, terminal_points: int = 3) -> ComputedResults:
    """从治理层数据计算全部确定性结果（不经过 LLM）。"""
    pk = calculate_pk_params(dataset, loq, terminal_points)
    qc = calculate_qc_summary(dataset, loq)
    tables = {
        "pk": build_pk_table(pk),
        "qc": build_qc_table(qc),
    }
    return ComputedResults(pk_by_subject=pk, qc_summary=qc, tables=tables)


__all__ = [
    "ComputedResults",
    "compute",
    "calculate_pk_params",
    "calculate_qc_summary",
    "build_pk_table",
    "build_qc_table",
]
