"""
检测能力管理接口。

提供模型增删改查、标签关联、REST 连接有效性检测、Python 脚本有效性检测。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import DetectionModel, ModelTagLink, SafetyTag, User
from app.schemas import (
    ModelCreate,
    ModelOut,
    ModelUpdate,
    ValidationResult,
)
from app.services.model_invoker import (
    validate_model_connectivity,
    validate_model_script,
)

router = APIRouter(prefix="/api/models", tags=["检测能力"])


def _tags_of(db: Session, model_id: int) -> list[SafetyTag]:
    """查询模型关联的标签列表。"""
    links = db.query(ModelTagLink).filter(ModelTagLink.model_id == model_id).all()
    if not links:
        return []
    ids = [l.tag_id for l in links]
    return db.query(SafetyTag).filter(SafetyTag.id.in_(ids)).all()


def _to_out(db: Session, model: DetectionModel) -> ModelOut:
    """将 ORM 模型转换为带标签的输出 Schema。"""
    out = ModelOut.model_validate(model)
    out.tags = [t for t in _tags_of(db, model.id)]  # type: ignore
    return out


def _set_tags(db: Session, model_id: int, tag_ids: list[int]) -> None:
    """重置模型的标签关联。"""
    db.query(ModelTagLink).filter(ModelTagLink.model_id == model_id).delete()
    for tid in set(tag_ids):
        if db.query(SafetyTag).filter(SafetyTag.id == tid).first():
            db.add(ModelTagLink(model_id=model_id, tag_id=tid))


@router.get("", response_model=list[ModelOut], summary="模型列表（含接入方式）")
def list_models(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    models = db.query(DetectionModel).order_by(DetectionModel.id.asc()).all()
    return [_to_out(db, m) for m in models]


@router.get("/{model_id}", response_model=ModelOut, summary="模型详情（含接入方式）")
def get_model(
    model_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    model = db.query(DetectionModel).filter(DetectionModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return _to_out(db, model)


@router.post("", response_model=ModelOut, summary="新增模型")
def create_model(
    payload: ModelCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if payload.access_type not in ("rest", "script"):
        raise HTTPException(status_code=400, detail="接入方式只能为 rest 或 script")
    if db.query(DetectionModel).filter(DetectionModel.name == payload.name).first():
        raise HTTPException(status_code=400, detail="模型名称已存在")

    data = payload.model_dump(exclude={"tag_ids"})
    model = DetectionModel(**data)
    db.add(model)
    db.flush()
    _set_tags(db, model.id, payload.tag_ids)
    db.commit()
    db.refresh(model)
    return _to_out(db, model)


@router.put("/{model_id}", response_model=ModelOut, summary="更新模型")
def update_model(
    model_id: int,
    payload: ModelUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    model = db.query(DetectionModel).filter(DetectionModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    data = payload.model_dump(exclude_unset=True, exclude={"tag_ids"})
    for k, v in data.items():
        setattr(model, k, v)
    if payload.tag_ids is not None:
        _set_tags(db, model.id, payload.tag_ids)
    db.commit()
    db.refresh(model)
    return _to_out(db, model)


@router.delete("/{model_id}", summary="删除模型")
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    model = db.query(DetectionModel).filter(DetectionModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    db.query(ModelTagLink).filter(ModelTagLink.model_id == model_id).delete()
    db.delete(model)
    db.commit()
    return {"ok": True}


@router.post(
    "/{model_id}/validate",
    response_model=ValidationResult,
    summary="有效性检测（REST 连接 / 脚本执行）",
)
async def validate_model(
    model_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    model = db.query(DetectionModel).filter(DetectionModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    if model.access_type == "rest":
        result = await validate_model_connectivity(model)
    else:
        result = await validate_model_script(model)
    return ValidationResult(**result)
