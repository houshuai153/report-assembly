"""数据库连接与会话管理（SQLAlchemy 2.0 + psycopg3）。

DATABASE_URL 由环境变量提供，docker-compose 里指向 pgvector 容器：
    postgresql+psycopg://report:report@db:5432/report_assembly
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://report:report@localhost:5432/report_assembly",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope():
    """事务型会话：成功提交，异常回滚，始终关闭。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """建表（幂等）。连接失败时给出明确提示。"""
    from .models import Base

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"无法连接数据库 {DATABASE_URL}。请先启动 PostgreSQL（如 `docker compose up -d db`），"
            f"或设置正确的 DATABASE_URL。原始错误：{exc}"
        ) from exc
