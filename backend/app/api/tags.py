"""安全标签管理接口：内置标签 + 用户自定义标签的增删改查。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import SafetyTag, User
from app.schemas import TagCreate, TagOut, TagUpdate

router = APIRouter(prefix="/api/tags", tags=["安全标签"])


@router.get("", response_model=list[TagOut], summary="标签列表")
def list_tags(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(SafetyTag).order_by(SafetyTag.id.asc()).all()


@router.post("", response_model=TagOut, summary="创建自定义标签")
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if db.query(SafetyTag).filter(SafetyTag.name == payload.name).first():
        raise HTTPException(status_code=400, detail="标签名称已存在")
    tag = SafetyTag(
        name=payload.name,
        description=payload.description,
        direction=payload.direction,
        risk_type=payload.risk_type or "其他",
        is_builtin=False,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.put("/{tag_id}", response_model=TagOut, summary="更新标签")
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    tag = db.query(SafetyTag).filter(SafetyTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if tag.is_builtin:
        # 内置标签仅允许补充说明，名称与风险类型固定
        if payload.description is not None:
            tag.description = payload.description
        if payload.direction is not None:
            tag.direction = payload.direction
    else:
        for field in ("description", "direction", "risk_type"):
            val = getattr(payload, field)
            if val is not None:
                setattr(tag, field, val)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}", summary="删除自定义标签")
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    tag = db.query(SafetyTag).filter(SafetyTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if tag.is_builtin:
        raise HTTPException(status_code=400, detail="内置标签不可删除")
    db.delete(tag)
    db.commit()
    return {"ok": True}
