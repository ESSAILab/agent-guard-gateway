"""
对外检测场景接口。

管理护栏对外暴露的检测路径：增删改查、启停、有序策略链、绑定 API Key。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.strategies import _to_out as strategy_to_out
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    ApiKey,
    ApiPath,
    ApiPathStrategyLink,
    Strategy,
    User,
)
from app.schemas import ApiPathCreate, ApiPathOut, ApiPathUpdate

router = APIRouter(prefix="/api/api-paths", tags=["检测场景"])


def _strategies_of(db: Session, api_path_id: int) -> list[Strategy]:
    """按顺序返回路径绑定的策略。"""
    links = (
        db.query(ApiPathStrategyLink)
        .filter(ApiPathStrategyLink.api_path_id == api_path_id)
        .order_by(ApiPathStrategyLink.order_index.asc())
        .all()
    )
    result = []
    for link in links:
        s = db.query(Strategy).filter(Strategy.id == link.strategy_id).first()
        if s:
            result.append(s)
    return result


def _to_out(db: Session, ap: ApiPath) -> ApiPathOut:
    out = ApiPathOut.model_validate(ap)
    out.strategies = [strategy_to_out(db, s) for s in _strategies_of(db, ap.id)]  # type: ignore
    return out


def _set_strategies(db: Session, api_path_id: int, strategy_ids: list[int]) -> None:
    """按给定顺序重置策略链。"""
    db.query(ApiPathStrategyLink).filter(
        ApiPathStrategyLink.api_path_id == api_path_id
    ).delete()
    for idx, sid in enumerate(dict.fromkeys(strategy_ids)):
        if db.query(Strategy).filter(Strategy.id == sid).first():
            db.add(
                ApiPathStrategyLink(
                    api_path_id=api_path_id, strategy_id=sid, order_index=idx
                )
            )


def _normalize_path(path: str) -> str:
    """规范化对外路径，确保以 / 开头。"""
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    return path


@router.get("", response_model=list[ApiPathOut], summary="API 路径列表")
def list_paths(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    items = db.query(ApiPath).order_by(ApiPath.id.asc()).all()
    return [_to_out(db, ap) for ap in items]


@router.get("/{path_id}", response_model=ApiPathOut, summary="API 路径详情")
def get_path(
    path_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    ap = db.query(ApiPath).filter(ApiPath.id == path_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="API 路径不存在")
    return _to_out(db, ap)


@router.post("", response_model=ApiPathOut, summary="创建 API 路径")
def create_path(
    payload: ApiPathCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    path = _normalize_path(payload.path)
    if db.query(ApiPath).filter(ApiPath.path == path).first():
        raise HTTPException(status_code=400, detail="该对外路径已存在")
    if payload.api_key_id and not db.query(ApiKey).filter(
        ApiKey.id == payload.api_key_id
    ).first():
        raise HTTPException(status_code=400, detail="指定的 API Key 不存在")

    ap = ApiPath(
        name=payload.name,
        path=path,
        description=payload.description,
        enabled=payload.enabled,
        api_key_id=payload.api_key_id,
    )
    db.add(ap)
    db.flush()
    _set_strategies(db, ap.id, payload.strategy_ids)
    db.commit()
    db.refresh(ap)
    return _to_out(db, ap)


@router.put("/{path_id}", response_model=ApiPathOut, summary="更新 API 路径")
def update_path(
    path_id: int,
    payload: ApiPathUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ap = db.query(ApiPath).filter(ApiPath.id == path_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="API 路径不存在")

    data = payload.model_dump(exclude_unset=True, exclude={"strategy_ids", "path"})
    for k, v in data.items():
        setattr(ap, k, v)
    if payload.path is not None:
        new_path = _normalize_path(payload.path)
        conflict = (
            db.query(ApiPath)
            .filter(ApiPath.path == new_path, ApiPath.id != path_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="该对外路径已存在")
        ap.path = new_path
    if payload.strategy_ids is not None:
        _set_strategies(db, ap.id, payload.strategy_ids)
    db.commit()
    db.refresh(ap)
    return _to_out(db, ap)


@router.delete("/{path_id}", summary="删除 API 路径")
def delete_path(
    path_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    ap = db.query(ApiPath).filter(ApiPath.id == path_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="API 路径不存在")
    db.query(ApiPathStrategyLink).filter(
        ApiPathStrategyLink.api_path_id == path_id
    ).delete()
    db.delete(ap)
    db.commit()
    return {"ok": True}
