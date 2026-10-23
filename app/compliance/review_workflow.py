"""人工审核工作流：审核者逐段接受 / 修改 / 拒绝，每个动作写审计链。

人工修改不覆盖 AI 生成的记录，而是追加 HUMAN_EDIT 记录，
形成"AI 生成 → 人修改 → 人批准"的完整序列。
"""

from __future__ import annotations

from .audit_chain import AuditChain
from .rbac import Role, User, actor_has_role
from app.generation.state_machine import ReportState


class ReviewWorkflow:
    def __init__(self, audit: AuditChain) -> None:
        self.audit = audit

    def claim(self, report, reviewer: User) -> None:
        """审核者认领报告：PENDING_REVIEW -> UNDER_REVIEW。"""
        self._require_role(reviewer, Role.REVIEWER)
        report.transition(ReportState.UNDER_REVIEW, actor=reviewer, audit=self.audit)

    def accept_section(self, report, reviewer: User, section_type: str) -> None:
        self._require_role(reviewer, Role.REVIEWER)
        draft = report.sections[section_type]
        self.audit.append(
            action="HUMAN_ACCEPT",
            actor=reviewer.id,
            object_type="section",
            object_id=section_type,
            payload_hash=self.audit.hash_text(draft.text),
            metadata={"decision": "accept", "section": section_type},
        )

    def edit_section(self, report, reviewer: User, section_type: str, new_text: str) -> None:
        self._require_role(reviewer, Role.REVIEWER)
        old = report.sections[section_type]
        report.sections[section_type] = old.model_copy(update={"text": new_text, "status": "edited"})
        self.audit.append(
            action="HUMAN_EDIT",
            actor=reviewer.id,
            object_type="section",
            object_id=section_type,
            payload_hash=self.audit.hash_text(new_text),
            metadata={"section": section_type, "previous_hash": self.audit.hash_text(old.text)},
        )

    def reject_section(self, report, reviewer: User, section_type: str, reason: str) -> None:
        self._require_role(reviewer, Role.REVIEWER)
        draft = report.sections[section_type]
        self.audit.append(
            action="HUMAN_REJECT",
            actor=reviewer.id,
            object_type="section",
            object_id=section_type,
            payload_hash=self.audit.hash_text(draft.text),
            metadata={"section": section_type, "reason": reason},
        )

    def approve(self, report, approver: User) -> None:
        """QA 批准放行：UNDER_REVIEW -> APPROVED（唯一可放行状态）。"""
        self._require_role(approver, Role.QA_APPROVER)
        report.transition(ReportState.APPROVED, actor=approver, audit=self.audit)

    @staticmethod
    def _require_role(user: User, role: Role) -> None:
        if not actor_has_role(user, role):
            raise PermissionError(f"{user.id} 缺少角色 {role.value}")
