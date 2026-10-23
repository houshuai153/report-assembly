"""状态机：人工审核节点不可绕过 + 批准权限的单元测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.compliance.rbac import Role, User
from app.generation.state_machine import IllegalTransitionError, ReportState, transition


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.analyst = User(id="a", name="分析师", roles=frozenset({Role.ANALYST}))
        self.qa = User(id="q", name="QA", roles=frozenset({Role.QA_APPROVER}))

    def test_ai_cannot_approve_directly(self):
        with self.assertRaises(IllegalTransitionError):
            transition(ReportState.AI_DRAFTED, ReportState.APPROVED, actor=self.qa)

    def test_ai_cannot_skip_queue(self):
        with self.assertRaises(IllegalTransitionError):
            transition(ReportState.AI_DRAFTED, ReportState.UNDER_REVIEW, actor=self.analyst)

    def test_approve_requires_qa_role(self):
        with self.assertRaises(PermissionError):
            transition(ReportState.UNDER_REVIEW, ReportState.APPROVED, actor=self.analyst)

    def test_qa_can_approve(self):
        state = transition(ReportState.UNDER_REVIEW, ReportState.APPROVED, actor=self.qa)
        self.assertEqual(state, ReportState.APPROVED)

    def test_valid_path(self):
        state = transition(ReportState.AI_DRAFTED, ReportState.PENDING_REVIEW)
        state = transition(state, ReportState.UNDER_REVIEW)
        self.assertEqual(state, ReportState.UNDER_REVIEW)


if __name__ == "__main__":
    unittest.main()
