"""持久化层：报告 + 章节 + 哈希链审计的 PostgreSQL 存储。

生产环境把状态从进程内存迁到 PostgreSQL：
  - 报告/章节：reports 表（JSONB 存元数据、计算结果、章节）
  - 审计链：audit_entries 表（append-only，按 report 分区，id 自增定序）
"""

from .repository import (
    SqlAuditChain,
    finalize_report,
    get_report,
    insert_report,
    list_reports,
    update_report_state,
    update_section,
)

__all__ = [
    "SqlAuditChain",
    "insert_report",
    "finalize_report",
    "get_report",
    "list_reports",
    "update_report_state",
    "update_section",
]
