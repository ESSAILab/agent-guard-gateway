"""
FastAPI 认证依赖。

- 管理后台接口：使用 JWT Bearer 令牌认证（登录用户）。
- 对外检测接口：使用 API Key 认证（见 services 层单独校验）。
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User

# tokenUrl 指向登录接口，供 OpenAPI 文档「Authorize」使用
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """从 JWT 解析当前登录用户，校验存在且启用。"""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或过期的登录凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = decode_access_token(token)
    if not username:
        raise credentials_exc
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.enabled:
        raise credentials_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员角色。"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return user
