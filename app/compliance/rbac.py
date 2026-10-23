"""角色权限：demo 的极简 RBAC。真实场景接企业身份源（LDAP/SSO）。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    ANALYST = "analyst"            # 触发生成、编辑初稿
    REVIEWER = "reviewer"          # 审核（接受/修改/拒绝）
    QA_APPROVER = "qa_approver"    # 批准放行（唯一可批准角色）


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    roles: frozenset[Role] = Field(default_factory=frozenset)


def actor_has_role(user: User, role: Role) -> bool:
    return role in user.roles
