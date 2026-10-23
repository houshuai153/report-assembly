"""已批准文本语料库（demo 内置样例）。

真实场景这些文本来自历史报告中经过 QA 放行的章节，入库前经过
清洗与去标识化，并按 report_type / matrix / platform / section_type 索引。
"""

from __future__ import annotations

from typing import Any

# 每一条都是一个"经过 QA 放行的可复用表述片段"。
_CORPUS: list[dict[str, Any]] = [
    # ---- 方法描述 ----
    {
        "id": "mth-001", "report_type": "clinical_bioanalysis",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "method_description",
        "text": "Sample preparation was performed by protein precipitation followed by "
                "reversed-phase liquid chromatography.",
    },
    {
        "id": "mth-002", "report_type": "clinical_bioanalysis",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "method_description",
        "text": "Analyte and internal standard were detected by tandem mass spectrometry "
                "in multiple reaction monitoring mode.",
    },
    {
        "id": "mth-003", "report_type": "clinical_bioanalysis",
        "matrix": "serum", "platform": "ELISA", "section_type": "method_description",
        "text": "Concentrations were determined using a validated sandwich ELISA.",
    },
    {
        "id": "mth-004", "report_type": "nonclinical_pk",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "method_description",
        "text": "Samples were analyzed across multiple analytical runs with bracketed "
                "calibration standards.",
    },

    # ---- 结果摘要 ----
    {
        "id": "res-001", "report_type": "clinical_bioanalysis",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "result_summary",
        "text": "Systemic exposure increased with dose and was consistent with the "
                "expected pharmacokinetic profile.",
    },
    {
        "id": "res-002", "report_type": "clinical_bioanalysis",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "result_summary",
        "text": "No unexpected accumulation was observed over the sampling interval.",
    },
    {
        "id": "res-003", "report_type": "nonclinical_pk",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "result_summary",
        "text": "Exposure (AUC) was roughly dose-proportional across the tested range.",
    },

    # ---- 质控总结 ----
    {
        "id": "qc-001", "report_type": "clinical_bioanalysis",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "qc_summary",
        "text": "Intra- and inter-run accuracy and precision of quality control samples "
                "were within the predefined acceptance limits.",
    },
    {
        "id": "qc-002", "report_type": "clinical_bioanalysis",
        "matrix": "plasma", "platform": "LC-MS/MS", "section_type": "qc_summary",
        "text": "Calibration curves were linear over the validated concentration range.",
    },
    {
        "id": "qc-003", "report_type": "clinical_bioanalysis",
        "matrix": "serum", "platform": "ELISA", "section_type": "qc_summary",
        "text": "All plate controls passed acceptance criteria on every analytical run.",
    },
]


def build_corpus() -> list[dict[str, Any]]:
    """返回语料库的一份拷贝。真实场景从 PostgreSQL / pgvector 读取。"""
    return [dict(doc) for doc in _CORPUS]
