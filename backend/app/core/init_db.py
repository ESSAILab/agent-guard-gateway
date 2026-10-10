"""
数据库初始化与种子数据。

- 建表（开发环境使用 create_all，生产可替换为迁移工具）。
- 创建默认管理员账户。
- 写入系统内置安全标签。
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import SafetyTag, User

# 系统内置安全标签：(名称, 风险类型, 默认检测方向, 说明)
BUILTIN_TAGS = [
    ("个人信息检测", "个人信息检测", "both", "检测消息中是否包含个人隐私信息"),
    ("偏离主题检测", "偏离主题检测", "both", "检测内容是否偏离预期主题范围"),
    ("越狱攻击检测", "越狱攻击检测", "input", "检测是否存在绕过模型安全限制的攻击"),
    ("幻觉/虚构检测", "幻觉/虚构检测", "output", "检测模型输出是否存在事实性虚构"),
    ("不当言论/低俗内容检测", "不当言论/低俗内容检测", "both", "检测不当或低俗内容"),
    ("提及竞品", "提及竞品", "both", "检测内容是否提及竞争对手品牌或产品"),
]


def init_db() -> None:
    """初始化数据库：建表 + 种子数据。"""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        _seed_admin(db)
        _seed_builtin_tags(db)
        db.commit()
    finally:
        db.close()


def _seed_admin(db: Session) -> None:
    """若不存在则创建默认管理员。"""
    existing = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
    if not existing:
        db.add(
            User(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                enabled=True,
            )
        )


def _seed_builtin_tags(db: Session) -> None:
    """写入内置安全标签（幂等）。"""
    for name, risk_type, direction, desc in BUILTIN_TAGS:
        existing = db.query(SafetyTag).filter(SafetyTag.name == name).first()
        if not existing:
            db.add(
                SafetyTag(
                    name=name,
                    description=desc,
                    is_builtin=True,
                    direction=direction,
                    risk_type=risk_type,
                )
            )
