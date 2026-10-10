"""用户管理接口（需管理员权限）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import hash_password
from app.models import User
from app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("", response_model=list[UserOut], summary="用户列表")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).order_by(User.id.asc()).all()


@router.post("", response_model=UserOut, summary="创建用户")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if payload.role not in ("admin", "operator"):
        raise HTTPException(status_code=400, detail="角色只能为 admin 或 operator")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        enabled=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut, summary="更新用户")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.role:
        if payload.role not in ("admin", "operator"):
            raise HTTPException(status_code=400, detail="角色只能为 admin 或 operator")
        user.role = payload.role
    if payload.enabled is not None:
        # 防止禁用自己导致无人可管理
        if user.id == admin.id and not payload.enabled:
            raise HTTPException(status_code=400, detail="不可禁用当前登录账户")
        user.enabled = payload.enabled
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", summary="删除用户")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不可删除当前登录账户")
    db.delete(user)
    db.commit()
    return {"ok": True}
