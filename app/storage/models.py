"""SQLAlchemy ORM 模型。

注意：列名用 meta 而非 metadata —— SQLAlchemy 的 Base 保留 metadata 作为 MetaData 注册表。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ReportRow(Base):
    __tablename__ = "reports"

    report_id = Column(String(32), primary_key=True)
    study_id = Column(String, nullable=False)
    state = Column(String, nullable=False)
    meta = Column(JSONB, nullable=False)        # 研究元数据（StudyMetadata）
    computed = Column(JSONB, nullable=False)    # {pk_by_subject, qc_summary}
    sections = Column(JSONB, nullable=False)    # {section_type: {...}}
    markdown = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class AuditEntryRow(Base):
    __tablename__ = "audit_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)  # 自增，定义追加顺序
    report_id = Column(String(32), ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False)
    entry_id = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    object_type = Column(String, nullable=False)
    object_id = Column(String, nullable=False)
    payload_hash = Column(String, nullable=False)
    previous_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False)
    tool = Column(String, nullable=True)
    meta = Column(JSONB, nullable=False)

    __table_args__ = (Index("ix_audit_report_id_id", "report_id", "id"),)
