"""确定性 PK 计算的单元测试（纯函数、可复现）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.generation.deterministic import compute
from app.governance.contracts import (
    ConcentrationRecord,
    DataStatus,
    GovernedDataset,
    StudyMetadata,
)


def make_dataset() -> GovernedDataset:
    meta = StudyMetadata(
        study_id="TST-1", analyte="A", matrix="plasma", species="human",
        method_platform="LC-MS/MS", report_type="clinical_bioanalysis",
    )
    records = [
        ConcentrationRecord(sample_id="s0", subject_id="S1", timepoint=0.0, concentration=100.0, run_id="R1"),
        ConcentrationRecord(sample_id="s1", subject_id="S1", timepoint=1.0, concentration=50.0, run_id="R1"),
        ConcentrationRecord(sample_id="s2", subject_id="S1", timepoint=2.0, concentration=25.0, run_id="R1"),
    ]
    return GovernedDataset(
        metadata=meta, concentrations=tuple(records),
        data_version="v1", status=DataStatus.LOCKED,
    )


class TestPkCalculator(unittest.TestCase):
    def setUp(self):
        self.dataset = make_dataset()

    def test_cmax_tmax(self):
        pk = compute(self.dataset).pk_by_subject["S1"]
        self.assertEqual(pk["Cmax"], 100.0)
        self.assertEqual(pk["Tmax"], 0.0)

    def test_auc_last_trapezoidal(self):
        pk = compute(self.dataset).pk_by_subject["S1"]
        # 0.5*(1-0)*(100+50) + 0.5*(2-1)*(50+25) = 75 + 37.5
        self.assertAlmostEqual(pk["AUC_last"], 112.5, places=6)

    def test_terminal_half_life(self):
        pk = compute(self.dataset).pk_by_subject["S1"]
        # 终末相三点等间距，kel = ln2，T1/2 = 1
        self.assertAlmostEqual(pk["T1_2"], 1.0, places=3)

    def test_auc_inf(self):
        pk = compute(self.dataset).pk_by_subject["S1"]
        # 112.5 + 25 / 0.69315 ≈ 148.57
        self.assertAlmostEqual(pk["AUC_inf"], 148.57, places=1)


if __name__ == "__main__":
    unittest.main()
