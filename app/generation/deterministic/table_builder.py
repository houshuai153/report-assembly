"""确定性表格构建：渲染 markdown 表格，不经过 LLM。

真实场景这里用 Jinja2 模板渲染 TFLs；demo 用轻量 markdown 表格表达同等语义。
"""

from __future__ import annotations


def _md_table(headers: list[str], rows: list[list]) -> str:
    header = "| " + " | ".join(str(h) for h in headers) + " |"
    sep = "|" + "|".join(" --- " for _ in headers) + "|"
    body = "\n".join(
        "| " + " | ".join("" if c is None else str(c) for c in row) + " |"
        for row in rows
    )
    return header + "\n" + sep + "\n" + body


def build_pk_table(pk_by_subject: dict[str, dict]) -> str:
    headers = ["Subject", "Cmax (ng/mL)", "Tmax (h)", "AUC_last (h·ng/mL)", "AUC_inf (h·ng/mL)", "T1/2 (h)"]
    rows = [
        [subj, p.get("Cmax"), p.get("Tmax"), p.get("AUC_last"), p.get("AUC_inf"), p.get("T1_2")]
        for subj, p in pk_by_subject.items()
    ]
    return _md_table(headers, rows)


def build_qc_table(qc: dict) -> str:
    headers = ["Metric", "Value"]
    rows = [
        ["Total samples", qc["total_samples"]],
        ["Below LLOQ (BLQ)", qc["below_loq"]],
        ["Measurable samples", qc["measurable"]],
        ["Analytical runs", qc["runs"]],
        ["Subjects", qc["subjects"]],
        ["LLOQ (ng/mL)", qc["lloq"]],
    ]
    return _md_table(headers, rows)
