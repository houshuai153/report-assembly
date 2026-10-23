"""第一层：源数据治理。

报告初稿的准确性上限由源数据质量决定。校验必须在数据进入治理层时完成，
报告生成层不做数据校验——报告层如果还需要"检查数据对不对"，说明治理层没闭合。
"""

from .contracts import (
    ConcentrationRecord,
    DataStatus,
    GovernedDataset,
    StudyMetadata,
)
from .service import GovernanceError, GovernanceService

__all__ = [
    "ConcentrationRecord",
    "DataStatus",
    "GovernedDataset",
    "StudyMetadata",
    "GovernanceError",
    "GovernanceService",
]
