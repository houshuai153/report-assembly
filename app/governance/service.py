"""治理层服务入口：接入 → 契约校验 → 业务校验 → 锁定 → 产出 GovernedDataset。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from .adapters import InlineAdapter, LimsAdapter
from .contracts import ConcentrationRecord, DataStatus, GovernedDataset, StudyMetadata
from .validators import validate_completeness, validate_qc


class GovernanceError(Exception):
    """数据未通过治理层校验，禁止进入报告生成。"""


class GovernanceService:
    def __init__(self, adapter: LimsAdapter | InlineAdapter | None = None) -> None:
        self.adapter = adapter or LimsAdapter()

    def ingest(self, source: str | list[dict[str, Any]], metadata: dict[str, Any]) -> GovernedDataset:
        """接入 + 校验 + 锁定。

        source 为 str 时按文件路径读取，为 list 时直接使用原始记录。
        """
        if isinstance(source, str):
            raw = self.adapter.read(source)  # type: ignore[union-attr]
        else:
            raw = source

        # 1. 契约校验：字段级 / 取值域由 Pydantic 在构造时强制
        try:
            meta = StudyMetadata(**metadata)
            records = [ConcentrationRecord(**r) for r in raw]
        except ValidationError as exc:
            raise GovernanceError(f"数据契约校验失败：{exc}") from exc

        # 2. 业务校验：跨记录规则（Pydantic 管不到的部分）
        for validator in (validate_qc, validate_completeness):
            result = validator(records)
            if not result.ok:
                raise GovernanceError("; ".join(result.errors))

        now = datetime.now(timezone.utc)
        return GovernedDataset(
            metadata=meta,
            concentrations=tuple(records),
            data_version=self._version(meta.study_id, now),
            status=DataStatus.LOCKED,
            locked_at=now,
        )

    @staticmethod
    def _version(study_id: str, now: datetime) -> str:
        return f"{study_id}-{now.strftime('%Y%m%d%H%M%S')}"
