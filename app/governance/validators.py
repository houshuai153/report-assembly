"""治理层业务规则校验：在数据进入治理层时完成，而不是在报告生成层。

字段级 / 取值域校验已由 Pydantic 契约（contracts.py）在构造时承担；
本模块只做跨记录的**业务规则**校验（完整性、重复、跨受试者一致性）。
"""

from __future__ import annotations

from .contracts import ConcentrationRecord


class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_qc(records: list[ConcentrationRecord]) -> ValidationResult:
    """跨记录质控规则：样本标识唯一性、BLQ 比例。"""
    res = ValidationResult()
    if not records:
        res.add_error("数据集为空，无法生成报告")
        return res

    sample_ids = [r.sample_id for r in records]
    if len(sample_ids) != len(set(sample_ids)):
        res.add_error("存在重复的 sample_id")

    blq = sum(1 for r in records if r.concentration is None)
    if blq / len(records) > 0.5:
        res.add_warning(f"BLQ 比例过高（{blq}/{len(records)}）")

    return res


def validate_completeness(records: list[ConcentrationRecord]) -> ValidationResult:
    """完整性：每个受试者必须有足够的采样点（用于估算 PK 参数）。"""
    res = ValidationResult()
    by_subject: dict[str, int] = {}
    for r in records:
        by_subject[r.subject_id] = by_subject.get(r.subject_id, 0) + 1

    for subject, n in by_subject.items():
        if n < 3:
            res.add_error(f"受试者 {subject} 采样点不足（{n} < 3），无法估算终末相")

    if len(by_subject) < 2:
        res.add_warning("受试者数量过少，PK 参数统计意义有限")

    return res
