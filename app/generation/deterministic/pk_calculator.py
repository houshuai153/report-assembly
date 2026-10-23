"""PK 参数计算：纯函数。

输入：受治理的浓度数据。
输出：Cmax、Tmax、AUC_last、AUC_inf、T1/2 等。
不依赖任何模型，审计时可直接展示计算逻辑。

用 LLM 算 Cmax 或 AUC 是拿确定性换不确定性，没有任何收益。
"""

from __future__ import annotations

import math

from app.governance.contracts import GovernedDataset


def _subject_series(dataset: GovernedDataset, subject_id: str) -> list[tuple[float, float | None]]:
    return sorted(
        (
            (r.timepoint, r.concentration)
            for r in dataset.concentrations
            if r.subject_id == subject_id
        ),
        key=lambda x: x[0],
    )


def _trapezoidal(pts: list[tuple[float, float]]) -> float:
    """线性梯形法计算 AUC，从 t0 到最后一个可定量点。"""
    auc = 0.0
    for i in range(len(pts) - 1):
        t0, c0 = pts[i]
        t1, c1 = pts[i + 1]
        auc += 0.5 * (t1 - t0) * (c0 + c1)
    return auc


def _kel(pts: list[tuple[float, float]], n: int = 3) -> float | None:
    """终末相 log-linear 回归估算消除速率常数 kel（取最后 n 个可定量点）。"""
    pts = [(t, c) for t, c in pts if c > 0]
    if len(pts) < n:
        n = len(pts)
    if n < 2:
        return None

    tail = pts[-n:]
    xs = [t for t, _ in tail]
    ys = [math.log(c) for _, c in tail]
    m = len(xs)

    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))

    denom = m * sxx - sx * sx
    if denom == 0:
        return None
    slope = (m * sxy - sx * sy) / denom
    return -slope  # kel = -slope


def calculate_pk_params(
    dataset: GovernedDataset,
    loq: float = 1.0,
    terminal_points: int = 3,
) -> dict[str, dict[str, float | None]]:
    """每个受试者计算 Cmax / Tmax / AUC_last / AUC_inf / T1/2。"""
    pk: dict[str, dict[str, float | None]] = {}
    for subject_id in sorted({r.subject_id for r in dataset.concentrations}):
        pts = _subject_series(dataset, subject_id)
        measurable = [(t, c) for t, c in pts if c is not None and c >= loq]
        if not measurable:
            continue

        cmax = max(c for _, c in measurable)
        tmax = next(t for t, c in measurable if c == cmax)
        auc_last = _trapezoidal(measurable)
        kel = _kel(measurable, terminal_points)
        clast = measurable[-1][1]
        auc_inf = auc_last + clast / kel if kel and kel > 0 else None
        t_half = math.log(2) / kel if kel and kel > 0 else None

        pk[subject_id] = {
            "Cmax": round(cmax, 3),
            "Tmax": tmax,
            "AUC_last": round(auc_last, 3),
            "AUC_inf": round(auc_inf, 3) if auc_inf is not None else None,
            "T1_2": round(t_half, 3) if t_half is not None else None,
        }
    return pk
