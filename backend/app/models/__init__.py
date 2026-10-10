"""
ORM 数据模型定义（全部集中在本模块，便于维护关系映射）。

涵盖：用户、API Key、安全标签、检测能力、策略编排、对外 API 路径、
以及可观测日志（用户请求日志、检测模型调用日志）。
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    """统一的 UTC 时间戳生成函数。"""
    return datetime.now(timezone.utc)


# =====================================================================
# 用户与 API Key
# =====================================================================
class User(Base):
    """系统用户。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    # 角色：admin（管理员）/ operator（操作员）
    role: Mapped[str] = mapped_column(String(32), default="operator")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ApiKey(Base):
    """对外接口的认证密钥。"""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    key_value: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# =====================================================================
# 安全标签
# =====================================================================
class SafetyTag(Base):
    """
    安全标签。系统内置标签 is_builtin=True；用户自定义标签可指定检测方向。

    direction: input(检测输入) / output(检测输出) / both(均可)。
    """

    __tablename__ = "safety_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    direction: Mapped[str] = mapped_column(String(16), default="both")
    # 对应对外响应的「风险类型」枚举值，便于结果归类
    risk_type: Mapped[str] = mapped_column(String(64), default="其他")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# 模型 <-> 标签 多对多关联表
class ModelTagLink(Base):
    """模型与安全标签的多对多关联。"""

    __tablename__ = "model_tag_links"
    __table_args__ = (UniqueConstraint("model_id", "tag_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"))
    tag_id: Mapped[int] = mapped_column(ForeignKey("safety_tags.id", ondelete="CASCADE"))


# =====================================================================
# 检测能力
# =====================================================================
class DetectionModel(Base):
    """
    安全检测模型。

    access_type:
      - rest:   通过 REST API 接入
      - script: 通过用户提供的 Python 脚本接入
    """

    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    access_type: Mapped[str] = mapped_column(String(16))  # rest / script
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # ---- REST 接入相关字段 ----
    endpoint_url: Mapped[str] = mapped_column(String(512), default="")
    http_method: Mapped[str] = mapped_column(String(16), default="POST")
    # 请求头（JSON 对象）
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    # 请求体模板（JSON），其中可用 {content} 占位符注入被检测内容
    body_template: Mapped[dict] = mapped_column(JSON, default=dict)

    # REST「安全」判定条件：
    #   1) 状态码等于 safe_status_code（为空则不校验状态码）
    #   2) 响应体经 safe_jsonpath 提取的值 包含 safe_expected_value
    safe_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safe_jsonpath: Mapped[str] = mapped_column(String(256), default="")
    safe_expected_value: Mapped[str] = mapped_column(String(256), default="")
    # REST 不安全提示信息提取：从响应体按该 JsonPath 提取字段
    prompt_jsonpath: Mapped[str] = mapped_column(String(256), default="")

    # ---- 脚本接入相关字段 ----
    # 用户提供的 Python 脚本内容；约定 detect(content) 返回 (code, message)
    # code==0 表示安全，message 为不安全提示
    script_content: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )


# =====================================================================
# 策略编排
# =====================================================================
class StrategyModelLink(Base):
    """策略与所选检测模型的多对多关联（策略的检测模型成员）。"""

    __tablename__ = "strategy_model_links"
    __table_args__ = (UniqueConstraint("strategy_id", "model_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("strategies.id", ondelete="CASCADE")
    )
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"))


class Strategy(Base):
    """
    策略编排：针对某一功能标签构建的检测模型集合及其调用规则。

    调用规则 rule_type：
      - sequential（顺序检测）：按顺序逐个调用检测模型，
        任一模型判定不安全即整体不安全；
      - random（随机检测）：从模型池中随机挑选 1 个检测模型调用，
        以该模型的判定作为整体结果。
    timeout_policy:
      - safe / unsafe: 单个检测模型超时后按安全或不安全计入
    """

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # 该策略对应的功能标签（如「个人信息检测」）
    tag_id: Mapped[int] = mapped_column(ForeignKey("safety_tags.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 调用规则：sequential（顺序检测）/ random（随机检测）
    rule_type: Mapped[str] = mapped_column(String(16), default="sequential")

    # 最长检测等待时间（秒）
    max_wait_seconds: Mapped[float] = mapped_column(Float, default=60.0)
    # 单模型超时处理：safe / unsafe
    timeout_policy: Mapped[str] = mapped_column(String(16), default="unsafe")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )


# =====================================================================
# 对外 检测场景
# =====================================================================
class ApiPathStrategyLink(Base):
    """API 路径与策略编排的有序关联（策略链）。"""

    __tablename__ = "api_path_strategy_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_path_id: Mapped[int] = mapped_column(
        ForeignKey("api_paths.id", ondelete="CASCADE")
    )
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"))
    # 调用顺序，越小越先执行
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class ApiPath(Base):
    """护栏系统对外暴露的检测 API 路径。"""

    __tablename__ = "api_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    # 对外路径，如 /guard/chat-input
    path: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 该路径使用的认证 API Key
    api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# =====================================================================
# 可观测日志
# =====================================================================
class RequestLog(Base):
    """用户请求/响应日志（含处理耗时）。"""

    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_path: Mapped[str] = mapped_column(String(256), index=True)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    request_body: Mapped[dict] = mapped_column(JSON, default=dict)
    response_body: Mapped[dict] = mapped_column(JSON, default=dict)
    # 最终结果：safe / unsafe
    result: Mapped[str] = mapped_column(String(16), index=True)
    risk_type: Mapped[str] = mapped_column(String(64), default="")
    business_code: Mapped[int] = mapped_column(Integer, default=200)
    # 处理耗时（毫秒）
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class DetectionLog(Base):
    """单个检测模型的调用日志（含处理耗时）。"""

    __tablename__ = "detection_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("request_logs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    strategy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_name: Mapped[str] = mapped_column(String(128), default="")
    model_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), default="")
    access_type: Mapped[str] = mapped_column(String(16), default="")
    request_detail: Mapped[str] = mapped_column(Text, default="")
    response_detail: Mapped[str] = mapped_column(Text, default="")
    # 单模型判定结果：safe / unsafe / timeout / error
    result: Mapped[str] = mapped_column(String(16), default="")
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
