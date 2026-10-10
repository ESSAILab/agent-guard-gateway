"""认证相关接口：登录、获取当前用户信息。"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas import TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """
    使用用户名 + 密码登录，返回 JWT 访问令牌。

    采用表单字段 username / password（兼容 OpenAPI 的 Authorize 按钮）。
    """
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    if not user.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账户已被禁用"
        )
    token = create_access_token(user.username)
    return TokenResponse(
        access_token=token, username=user.username, role=user.role
    )


@router.get("/me", response_model=UserOut, summary="获取当前登录用户")
def me(user: User = Depends(get_current_user)):
    return user
