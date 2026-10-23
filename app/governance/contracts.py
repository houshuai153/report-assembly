"""治理层输出的数据契约（事实底座）。

企业级用 Pydantic v2 定义强类型契约：
  - 强类型：报告生成层只接受 GovernedDataset，不接受原始文件路径；
    数据没进治理层，生成层在类型层面就拿不到。
  - 字段级校验：Field 约束（长度、取值域）在构造时立即生效，
    extra="forbid" 拒绝任何未声明的字段。
  - 不可变：frozen 模型 + tuple，锁定后不可就地篡改。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DataStatus(str, Enum):
    RAW = "raw"
    QC_PASSED = "qc_passed"
    LOCKED = "locked"          # 锁定后不可修改，只能走变更流程


# 取值域用 Literal 收紧，非法基质/平台/报告类型在构造时即被拒绝
Matrix = Literal["plasma", "serum", "urine", "whole_blood", "csf", "other"]
Platform = Literal["LC-MS/MS", "ELISA", "LBA", "other"]
ReportType = Literal["clinical_bioanalysis", "nonclinical_pk", "toxicology", "other"]


class StudyMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    study_id: str = Field(min_length=1, description="研究编号")
    analyte: str = Field(min_length=1, description="分析物")
    matrix: Matrix = Field(description="基质")
    species: str = Field(min_length=1, description="物种")
    method_platform: Platform = Field(description="方法平台")
    report_type: ReportType = Field(description="报告类型")


class ConcentrationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    timepoint: float = Field(ge=0, description="采样时间点")
    concentration: float | None = Field(
        default=None, ge=0, description="浓度；None = BLQ（低于定量下限）"
    )
    run_id: str = Field(min_length=1)


class GovernedDataset(BaseModel):
    """治理层输出的唯一数据对象。报告生成只消费这个，不消费原始文件。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: StudyMetadata
    concentrations: tuple[ConcentrationRecord, ...]
    data_version: str = Field(min_length=1)
    status: DataStatus
    locked_at: datetime | None = None
