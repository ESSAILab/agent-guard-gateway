"""
可观测接口：用户请求日志、检测模型调用日志、统计汇总。

可按可观测级别（debug / basic / statistics）控制返回的明细丰富程度。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    ApiPath,
    DetectionLog,
    DetectionModel,
    RequestLog,
    Strategy,
    User,
)
from app.schemas import DetectionLogOut, Page, RequestLogOut, StatsSummary

router = APIRouter(prefix="/api/observability", tags=["可观测"])


@router.get("/level", summary="当前可观测级别")
def get_level(_: User = Depends(get_current_user)):
    """返回系统配置的可观测信息级别。"""
    return {"level": settings.OBSERVABILITY_LEVEL}


@router.get(
    "/request-logs",
    response_model=Page[RequestLogOut],
    summary="用户请求/响应日志（含耗时，分页）",
)
def request_logs(
    result: Optional[str] = Query(None, description="按结果过滤：safe / unsafe"),
    api_path: Optional[str] = Query(None, description="按对外路径部分匹配过滤"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(50, ge=1, le=500, description="每页条数，默认 50"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(RequestLog)
    if result:
        q = q.filter(RequestLog.result == result)
    if api_path:
        q = q.filter(RequestLog.api_path.like(f"%{api_path}%"))

    total = q.with_entities(func.count(RequestLog.id)).scalar() or 0
    logs = (
        q.order_by(RequestLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 批量统计每个请求关联的检测模型安全/不安全数量
    if logs:
        ids = [log.id for log in logs]
        rows = (
            db.query(DetectionLog.request_log_id, DetectionLog.result, func.count(DetectionLog.id))
            .filter(DetectionLog.request_log_id.in_(ids))
            .group_by(DetectionLog.request_log_id, DetectionLog.result)
            .all()
        )
        stats = {}
        for rid, res, cnt in rows:
            stats.setdefault(rid, {})[res] = cnt
        for log in logs:
            log.safe_count = stats.get(log.id, {}).get("safe", 0)
            log.unsafe_count = stats.get(log.id, {}).get("unsafe", 0)

    return Page(items=logs, total=total, page=page, page_size=page_size)


@router.delete(
    "/request-logs/purge",
    summary="清理指定天数以前的检测记录",
)
def purge_request_logs(
    days: int = Query(..., ge=1, description="删除多少天以前的记录"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """删除创建时间早于当前时刻 days 天之前的用户请求日志及其关联检测日志。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    old_log_ids = [
        rid
        for (rid,) in db.query(RequestLog.id)
        .filter(RequestLog.created_at < cutoff)
        .all()
    ]
    if not old_log_ids:
        return {"deleted": 0}

    det_deleted = (
        db.query(func.count(DetectionLog.id))
        .filter(DetectionLog.request_log_id.in_(old_log_ids))
        .scalar()
        or 0
    )
    # 关联检测日志依赖外键 ondelete=CASCADE，SQLite 默认不开启级联，显式删除一次
    db.query(DetectionLog).filter(
        DetectionLog.request_log_id.in_(old_log_ids)
    ).delete(synchronize_session=False)
    db.query(RequestLog).filter(RequestLog.id.in_(old_log_ids)).delete(
        synchronize_session=False
    )
    db.commit()
    return {"deleted": len(old_log_ids), "detection_logs_deleted": det_deleted}


@router.get(
    "/detection-logs",
    response_model=list[DetectionLogOut],
    summary="检测模型请求/响应日志（含耗时）",
)
def detection_logs(
    request_log_id: Optional[int] = Query(None, description="按请求日志 ID 过滤"),
    model_name: Optional[str] = Query(None, description="按模型名称过滤"),
    limit: int = Query(200, description="返回条数上限", le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(DetectionLog)
    if request_log_id:
        q = q.filter(DetectionLog.request_log_id == request_log_id)
    if model_name:
        q = q.filter(DetectionLog.model_name == model_name)
    return (
        q.order_by(DetectionLog.created_at.desc()).offset(offset).limit(limit).all()
    )


@router.get("/stats", response_model=StatsSummary, summary="统计汇总（大屏/概览）")
def stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total = db.query(func.count(RequestLog.id)).scalar() or 0
    safe = (
        db.query(func.count(RequestLog.id))
        .filter(RequestLog.result == "safe")
        .scalar()
        or 0
    )
    unsafe = (
        db.query(func.count(RequestLog.id))
        .filter(RequestLog.result == "unsafe")
        .scalar()
        or 0
    )
    avg_latency = db.query(func.avg(RequestLog.latency_ms)).scalar() or 0.0

    # 风险类型分布
    rows = (
        db.query(RequestLog.risk_type, func.count(RequestLog.id))
        .filter(RequestLog.result == "unsafe")
        .group_by(RequestLog.risk_type)
        .all()
    )
    risk_dist = {(rt or "其他"): cnt for rt, cnt in rows}

    # 近 7 日趋势
    trend = []
    now = datetime.now(timezone.utc)
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)
        day_total = (
            db.query(func.count(RequestLog.id))
            .filter(RequestLog.created_at >= day_start, RequestLog.created_at < day_end)
            .scalar()
            or 0
        )
        day_unsafe = (
            db.query(func.count(RequestLog.id))
            .filter(
                RequestLog.created_at >= day_start,
                RequestLog.created_at < day_end,
                RequestLog.result == "unsafe",
            )
            .scalar()
            or 0
        )
        trend.append(
            {
                "date": day_start.strftime("%m-%d"),
                "total": day_total,
                "unsafe": day_unsafe,
            }
        )

    return StatsSummary(
        total_requests=total,
        safe_count=safe,
        unsafe_count=unsafe,
        avg_latency_ms=round(float(avg_latency), 2),
        model_count=db.query(func.count(DetectionModel.id)).scalar() or 0,
        strategy_count=db.query(func.count(Strategy.id)).scalar() or 0,
        api_path_count=db.query(func.count(ApiPath.id)).scalar() or 0,
        risk_type_distribution=risk_dist,
        recent_trend=trend,
    )
