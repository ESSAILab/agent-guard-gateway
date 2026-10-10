"""
策略编排管理接口。

策略 = 针对某功能标签的检测模型集合 + 调用规则：
sequential（顺序检测）或 random（随机检测）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.models import _to_out as model_to_out
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    DetectionModel,
    SafetyTag,
    Strategy,
    StrategyModelLink,
    User,
)
from app.schemas import StrategyCreate, StrategyOut, StrategyUpdate

router = APIRouter(prefix="/api/strategies", tags=["策略编排"])


def _models_of(db: Session, strategy_id: int) -> list[DetectionModel]:
    links = (
        db.query(StrategyModelLink)
        .filter(StrategyModelLink.strategy_id == strategy_id)
        .all()
    )
    if not links:
        return []
    ids = [l.model_id for l in links]
    return db.query(DetectionModel).filter(DetectionModel.id.in_(ids)).all()


def _to_out(db: Session, strategy: Strategy) -> StrategyOut:
    out = StrategyOut.model_validate(strategy)
    out.models = [model_to_out(db, m) for m in _models_of(db, strategy.id)]  # type: ignore
    return out


def _validate_model_count(model_count: int) -> None:
    """校验至少选择 1 个检测模型。"""
    if model_count < 1:
        raise HTTPException(status_code=400, detail="至少选择 1 个检测模型")


def _set_models(db: Session, strategy_id: int, model_ids: list[int]) -> None:
    db.query(StrategyModelLink).filter(
        StrategyModelLink.strategy_id == strategy_id
    ).delete()
    for mid in dict.fromkeys(model_ids):  # 保序去重
        if db.query(DetectionModel).filter(DetectionModel.id == mid).first():
            db.add(StrategyModelLink(strategy_id=strategy_id, model_id=mid))


@router.get("", response_model=list[StrategyOut], summary="策略列表")
def list_strategies(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    items = db.query(Strategy).order_by(Strategy.id.asc()).all()
    return [_to_out(db, s) for s in items]


@router.get("/{strategy_id}", response_model=StrategyOut, summary="策略详情")
def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="策略不存在")
    return _to_out(db, s)


@router.post("", response_model=StrategyOut, summary="创建策略")
def create_strategy(
    payload: StrategyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not db.query(SafetyTag).filter(SafetyTag.id == payload.tag_id).first():
        raise HTTPException(status_code=400, detail="指定的功能标签不存在")
    if db.query(Strategy).filter(Strategy.name == payload.name).first():
        raise HTTPException(status_code=400, detail="策略名称已存在")
    _validate_model_count(len(payload.model_ids))

    data = payload.model_dump(exclude={"model_ids"})
    s = Strategy(**data)
    db.add(s)
    db.flush()
    _set_models(db, s.id, payload.model_ids)
    db.commit()
    db.refresh(s)
    return _to_out(db, s)


@router.put("/{strategy_id}", response_model=StrategyOut, summary="更新策略")
def update_strategy(
    strategy_id: int,
    payload: StrategyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="策略不存在")

    # 计算更新后的模型集合用于参数校验
    new_model_ids = payload.model_ids if payload.model_ids is not None else [
        l.model_id
        for l in db.query(StrategyModelLink).filter(
            StrategyModelLink.strategy_id == strategy_id
        ).all()
    ]
    _validate_model_count(len(new_model_ids))

    data = payload.model_dump(exclude_unset=True, exclude={"model_ids"})
    for k, v in data.items():
        setattr(s, k, v)
    if payload.model_ids is not None:
        _set_models(db, s.id, payload.model_ids)
    db.commit()
    db.refresh(s)
    return _to_out(db, s)


@router.delete("/{strategy_id}", summary="删除策略")
def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="策略不存在")
    db.query(StrategyModelLink).filter(
        StrategyModelLink.strategy_id == strategy_id
    ).delete()
    db.delete(s)
    db.commit()
    return {"ok": True}
