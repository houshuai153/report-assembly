"""报告状态机：人工审核节点不可绕过。

"AI 不能自己批准报告"不是靠流程约定，而是合法转换表里根本没有那条边。
"""

from __future__ import annotations

from enum import Enum

from app.compliance.rbac import Role, User, actor_has_role


class ReportState(str, Enum):
    INITIALIZED = "initialized"
    DATA_GOVERNED = "data_governed"
    AI_DRAFTED = "ai_drafted"          # AI 初稿完成，强制进入待审
    PENDING_REVIEW = "pending_review"  # 人工审核队列
    UNDER_REVIEW = "under_review"      # 审核者已认领
    REVISION_REQUIRED = "revision_required"
    APPROVED = "approved"              # 唯一可放行状态
    REJECTED = "rejected"


ALLOWED_TRANSITIONS: dict[ReportState, list[ReportState]] = {
    ReportState.INITIALIZED: [ReportState.DATA_GOVERNED],
    ReportState.DATA_GOVERNED: [ReportState.AI_DRAFTED],
    ReportState.AI_DRAFTED: [ReportState.PENDING_REVIEW],
    ReportState.PENDING_REVIEW: [ReportState.UNDER_REVIEW],
    ReportState.UNDER_REVIEW: [
        ReportState.APPROVED,
        ReportState.REVISION_REQUIRED,
        ReportState.REJECTED,
    ],
    ReportState.REVISION_REQUIRED: [ReportState.PENDING_REVIEW],
    # 注意：没有从 AI_DRAFTED 直接到 APPROVED 的路径。
}


class IllegalTransitionError(Exception):
    pass


def transition(
    state: ReportState,
    target: ReportState,
    actor: User | None = None,
    audit=None,
    report_id: str = "",
) -> ReportState:
    """执行状态迁移，非法迁移抛异常，批准需要 QA 角色。"""
    if target not in ALLOWED_TRANSITIONS.get(state, []):
        raise IllegalTransitionError(f"{state.value} -> {target.value} 不允许：审核节点不可绕过")

    if target == ReportState.APPROVED and (
        actor is None or not actor_has_role(actor, Role.QA_APPROVER)
    ):
        raise PermissionError("只有 QA 角色可以批准报告")

    if audit is not None:
        audit.append(
            action=f"STATE_{target.name}",
            actor=actor.id if actor else "system",
            object_type="report",
            object_id=report_id,
            payload_hash="",
            metadata={"from": state.value, "to": target.value},
        )

    return target
