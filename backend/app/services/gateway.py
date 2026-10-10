"""
护栏检测网关编排服务。

针对某个对外 API 路径：
  1) 提取被检测内容（按 JsonPath，失败则判不安全）；
  2) 按用户指定顺序逐个执行策略链；
  3) 任一策略不安全即整体不安全；
  4) 记录可观测日志，并通过广播器推送大屏事件。
"""
import json
import time
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    ApiPath,
    ApiPathStrategyLink,
    DetectionLog,
    DetectionModel,
    RequestLog,
    SafetyTag,
    Strategy,
    StrategyModelLink,
)
from app.schemas import GuardRequest, GuardResponse
from app.services.broadcaster import broadcaster
from app.services.model_invoker import extract_jsonpath
from app.services.strategy_engine import StrategyResult, execute_strategy

# 业务码定义
CODE_SAFE = 200          # 检测通过（安全）
CODE_UNSAFE = 4030       # 检测到风险（不安全）
CODE_EXTRACT_FAIL = 4001 # 内容提取失败


def _ordered_strategies(db: Session, api_path: ApiPath) -> List[Strategy]:
    """按 order_index 返回该路径启用的策略链。"""
    links = (
        db.query(ApiPathStrategyLink)
        .filter(ApiPathStrategyLink.api_path_id == api_path.id)
        .order_by(ApiPathStrategyLink.order_index.asc())
        .all()
    )
    strategies: List[Strategy] = []
    for link in links:
        s = db.query(Strategy).filter(Strategy.id == link.strategy_id).first()
        if s and s.enabled:
            strategies.append(s)
    return strategies


def _strategy_models(db: Session, strategy: Strategy) -> List[DetectionModel]:
    """获取策略关联的检测模型列表。"""
    links = (
        db.query(StrategyModelLink)
        .filter(StrategyModelLink.strategy_id == strategy.id)
        .all()
    )
    ids = [l.model_id for l in links]
    if not ids:
        return []
    return db.query(DetectionModel).filter(DetectionModel.id.in_(ids)).all()


def _extract_content(req: GuardRequest) -> Tuple[Optional[str], Optional[str]]:
    """
    提取被检测内容。

    返回 (content, error)。当 jsonpath 为空时检测整个消息；
    当提取失败时返回错误信息（调用方据此判不安全）。
    """
    if not req.jsonpath:
        return req.messages, None

    # 先尝试将消息解析为 JSON，再按 JsonPath 提取
    try:
        data = json.loads(req.messages)
    except Exception:
        return None, "被检测消息不是合法 JSON，无法按 JsonPath 提取"

    value = extract_jsonpath(data, req.jsonpath)
    if value is None:
        return None, f"JsonPath「{req.jsonpath}」未能从消息中提取到内容"
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return value, None


async def run_detection(
    db: Session,
    api_path: ApiPath,
    req: GuardRequest,
    client_ip: str,
) -> GuardResponse:
    """执行一次完整的护栏检测，并落库 + 广播。"""
    start = time.perf_counter()

    await broadcaster.broadcast(
        "request_received",
        {"api_path": api_path.path, "client_ip": client_ip},
    )

    # 1) 提取被检测内容
    content, err = _extract_content(req)
    if err is not None:
        resp = GuardResponse(
            code=CODE_EXTRACT_FAIL,
            risk_level="LOW",
            message=err,
            risk_type="其他",
        )
        await _persist(
            db, api_path, req, resp, "unsafe", client_ip,
            (time.perf_counter() - start) * 1000, [],
        )
        await broadcaster.broadcast(
            "final_result",
            {"api_path": api_path.path, "result": "unsafe", "reason": err},
        )
        return resp

    # 2) 顺序执行策略链
    strategies = _ordered_strategies(db, api_path)
    strategy_results: List[StrategyResult] = []
    final_safe = True
    final_message = ""
    final_risk_type = ""

    for strategy in strategies:
        tag = db.query(SafetyTag).filter(SafetyTag.id == strategy.tag_id).first()
        risk_type = tag.risk_type if tag else "其他"
        models = _strategy_models(db, strategy)

        await broadcaster.broadcast(
            "strategy_start",
            {
                "strategy": strategy.name,
                "rule_type": strategy.rule_type,
                "model_count": len(models),
            },
        )

        result = await execute_strategy(strategy, models, content, risk_type)
        strategy_results.append(result)

        # 推送每个检测模型的判定（用于大屏顺序检测动画）
        await broadcaster.broadcast(
            "strategy_result",
            {
                "strategy": strategy.name,
                "rule_type": result.rule_type,
                "safe": result.safe,
                "invoked": result.invoked_count,
                "safe_count": result.safe_count,
                "threshold": result.threshold,
                "models": [
                    {
                        "name": r.model_name,
                        "access_type": r.access_type,
                        "status": r.status,
                        "safe": r.safe,
                        "latency_ms": round(r.latency_ms, 1),
                    }
                    for r in result.model_results
                ],
            },
        )

        # 3) 任一策略不安全即整体不安全（并停止后续策略）
        if not result.safe:
            final_safe = False
            final_message = result.prompt_message or "检测到安全风险"
            final_risk_type = result.risk_type or "其他"
            break

    # 4) 构造对外响应
    if final_safe:
        resp = GuardResponse(
            code=CODE_SAFE, risk_level="NONE", message="检测通过，未发现安全风险",
            risk_type="",
        )
        result_flag = "safe"
    else:
        resp = GuardResponse(
            code=CODE_UNSAFE, risk_level="HIGH", message=final_message,
            risk_type=final_risk_type,
        )
        result_flag = "unsafe"

    latency = (time.perf_counter() - start) * 1000
    await _persist(
        db, api_path, req, resp, result_flag, client_ip, latency, strategy_results
    )
    await broadcaster.broadcast(
        "final_result",
        {
            "api_path": api_path.path,
            "result": result_flag,
            "risk_type": resp.risk_type,
            "latency_ms": round(latency, 1),
        },
    )
    return resp


async def _persist(
    db: Session,
    api_path: ApiPath,
    req: GuardRequest,
    resp: GuardResponse,
    result_flag: str,
    client_ip: str,
    latency_ms: float,
    strategy_results: List[StrategyResult],
) -> None:
    """落库请求日志与各检测模型调用日志。"""
    req_log = RequestLog(
        api_path=api_path.path,
        client_ip=client_ip,
        request_body=req.model_dump(),
        response_body=resp.model_dump(),
        result=result_flag,
        risk_type=resp.risk_type,
        business_code=resp.code,
        latency_ms=latency_ms,
    )
    db.add(req_log)
    db.flush()  # 取得 req_log.id

    for sr in strategy_results:
        for mr in sr.model_results:
            db.add(
                DetectionLog(
                    request_log_id=req_log.id,
                    strategy_id=sr.strategy_id,
                    strategy_name=sr.strategy_name,
                    model_id=mr.model_id,
                    model_name=mr.model_name,
                    access_type=mr.access_type,
                    request_detail=mr.request_detail[:4000],
                    response_detail=mr.response_detail[:4000],
                    result=mr.status,
                    latency_ms=mr.latency_ms,
                )
            )
    db.commit()
