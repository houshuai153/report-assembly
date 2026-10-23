"""第四层：合规锚定。

21 CFR Part 11 要求电子记录具备可归因性、同步性、原始性。
审计追踪必须能回答"谁、在什么时候、做了什么"，并且：
  - AI 输出与人类审核动作的审计链分离但关联；
  - 人工"在环"不是可选项，而是状态机的硬约束。
"""

from .audit_chain import AuditChain, AuditEntry, hash_text
from .rbac import Role, User, actor_has_role

__all__ = ["AuditChain", "AuditEntry", "hash_text", "Role", "User", "actor_has_role"]
