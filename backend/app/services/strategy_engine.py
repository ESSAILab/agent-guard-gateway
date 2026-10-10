"""
策略编排执行引擎。

支持两种调用规则：
- sequential（顺序检测）：按顺序逐个调用检测模型，任一模型判定不安全即整体不安全；
- random（随机检测）：从模型池中随机挑选 1 个检测模型调用，以该模型的判定作为整体结果。

并处理最长等待时间与单模型超时策略。
"""
import random
import time
from dataclasses import dataclass, field
from typing import List

from app.models import DetectionModel, Strategy
from app.services.model_invoker import InvokeResult, invoke_model

# 支持的调用规则
RULE_SEQUENTIAL = "sequential"
RULE_RANDOM = "random"
VALID_RULE_TYPES = {RULE_SEQUENTIAL, RULE_RANDOM}


@dataclass
class StrategyResult:
    """单条策略的整体执行结果。"""

    strategy_id: int
    strategy_name: str
    safe: bool
    # 触发不安全时的提示信息
    prompt_message: str = ""
    risk_type: str = ""
    # 执行统计：调用数 / 判安全数 / 阈值
    invoked_count: int = 0
    safe_count: int = 0
    threshold: int = 0
    rule_type: str = ""
    # 各模型执行详情，供可观测与大屏展示
    model_results: List[InvokeResult] = field(default_factory=list)
    latency_ms: float = 0.0


def _apply_timeout_policy(result: InvokeResult, policy: str) -> bool:
    """对超时结果应用策略：safe -> 视为安全；unsafe -> 视为不安全。"""
    if result.status == "timeout":
        return policy == "safe"
    return result.safe


async def execute_strategy(
    strategy: Strategy,
    models: List[DetectionModel],
    content: str,
    risk_type: str,
) -> StrategyResult:
    """执行单条策略编排，返回整体结果。"""
    start = time.perf_counter()
    enabled_models = [m for m in models if m.enabled]
    rule_type = strategy.rule_type if strategy.rule_type in VALID_RULE_TYPES else RULE_SEQUENTIAL
    result = StrategyResult(
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        safe=True,
        risk_type=risk_type,
        rule_type=rule_type,
    )

    if not enabled_models:
        # 无可用模型：保守起见判为不安全
        result.safe = False
        result.prompt_message = "策略未配置可用的检测模型"
        result.latency_ms = (time.perf_counter() - start) * 1000
        return result

    timeout = strategy.max_wait_seconds or 60.0
    if rule_type == RULE_RANDOM:
        await _run_random(strategy, enabled_models, content, timeout, result)
    else:
        await _run_sequential(strategy, enabled_models, content, timeout, result)

    result.latency_ms = (time.perf_counter() - start) * 1000
    return result


async def _run_random(
    strategy: Strategy,
    models: List[DetectionModel],
    content: str,
    timeout: float,
    result: StrategyResult,
) -> None:
    """随机调用规则：从模型池中随机挑选 1 个检测模型调用，以其判定作为整体结果。"""
    m = random.choice(models)
    # 仅调用 1 个模型，最长等待时间直接作为该模型的超时预算
    r = await invoke_model(m, content, timeout)

    is_safe = _apply_timeout_policy(r, strategy.timeout_policy)
    result.model_results.append(r)
    result.invoked_count = 1
    result.safe_count = 1 if is_safe else 0
    result.threshold = 1
    result.safe = is_safe
    if not is_safe:
        result.prompt_message = r.prompt_message or "检测到安全风险"


async def _run_sequential(
    strategy: Strategy,
    models: List[DetectionModel],
    content: str,
    timeout: float,
    result: StrategyResult,
) -> None:
    """顺序调用规则：逐个调用，任一不安全立即返回不安全。"""
    deadline = time.perf_counter() + timeout
    safe_count = 0
    for m in models:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            # 超过最长等待时间，按超时策略处理剩余
            r = InvokeResult(
                safe=(strategy.timeout_policy == "safe"),
                status="timeout",
                model_id=m.id,
                model_name=m.name,
                access_type=m.access_type,
                response_detail="超过最长检测等待时间",
            )
        else:
            r = await invoke_model(m, content, remaining)

        is_safe = _apply_timeout_policy(r, strategy.timeout_policy)
        result.model_results.append(r)
        result.invoked_count += 1
        if is_safe:
            safe_count += 1
        else:
            # 顺序规则下，任一不安全即整体不安全
            result.safe = False
            result.safe_count = safe_count
            result.threshold = 1
            result.prompt_message = r.prompt_message or "检测到安全风险"
            return

    result.safe = True
    result.safe_count = safe_count
    result.threshold = 1
