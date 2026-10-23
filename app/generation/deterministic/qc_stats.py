"""质控统计：纯函数。"""

from __future__ import annotations

from app.governance.contracts import GovernedDataset


def calculate_qc_summary(dataset: GovernedDataset, loq: float = 1.0) -> dict:
    records = dataset.concentrations
    total = len(records)
    below_loq = sum(
        1 for r in records if r.concentration is None or r.concentration < loq
    )
    run_ids = sorted({r.run_id for r in records})
    subject_ids = sorted({r.subject_id for r in records})

    return {
        "total_samples": total,
        "below_loq": below_loq,
        "measurable": total - below_loq,
        "runs": len(run_ids),
        "run_ids": run_ids,
        "subjects": len(subject_ids),
        "subject_ids": subject_ids,
        "lloq": loq,
    }
