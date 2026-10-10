"""令牌管理接口。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import generate_api_key
from app.models import ApiKey, User
from app.schemas import ApiKeyCreate, ApiKeyOut

router = APIRouter(prefix="/api/api-keys", tags=["令牌管理"])


@router.get("", response_model=list[ApiKeyOut], summary="API Key 列表")
def list_keys(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(ApiKey).order_by(ApiKey.id.asc()).all()


@router.post("", response_model=ApiKeyOut, summary="生成 API Key")
def create_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    key = ApiKey(name=payload.name, key_value=generate_api_key(), enabled=True)
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


@router.put("/{key_id}/toggle", response_model=ApiKeyOut, summary="启用/禁用 API Key")
def toggle_key(
    key_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    key.enabled = not key.enabled
    db.commit()
    db.refresh(key)
    return key


@router.delete("/{key_id}", summary="删除 API Key")
def delete_key(
    key_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    db.delete(key)
    db.commit()
    return {"ok": True}
