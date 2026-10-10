"""
数据库连接与会话管理。

使用 SQLAlchemy 2.x 风格。默认使用 SQLite，便于本地开发；
通过 DATABASE_URL 可切换到 PostgreSQL 等生产数据库。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# SQLite 需要关闭同线程检查，以便 FastAPI 多线程访问
connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    pass


def get_db():
    """FastAPI 依赖：提供一个数据库会话，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
