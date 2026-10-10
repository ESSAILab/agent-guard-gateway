"""
Pydantic 数据校验与序列化模型（请求/响应 Schema）。

按业务域分区组织：认证、用户、API Key、标签、模型、策略、API 路径、
对外检测接口、可观测日志。
"""
from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页响应。"""

    items: List[T]
    total: int
    page: int
    page_size: int


# =====================================================================
# 通用
# =====================================================================
class ORMBase(BaseModel):
    """启用 ORM 属性读取的基类。"""

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# 认证
# =====================================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


# =====================================================================
# 用户
# =====================================================================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4)
    role: str = Field("operator", description="admin 或 operator")


class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=4)
    role: Optional[str] = None
    enabled: Optional[bool] = None


class UserOut(ORMBase):
    id: int
    username: str
    role: str
    enabled: bool
    created_at: datetime


# =====================================================================
# API Key
# =====================================================================
class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyOut(ORMBase):
    id: int
    name: str
    key_value: str
    enabled: bool
    created_at: datetime


# =====================================================================
# 安全标签
# =====================================================================
class TagCreate(BaseModel):
    name: str
    description: str = ""
    direction: str = Field("both", description="input / output / both")
    risk_type: str = "其他"


class TagUpdate(BaseModel):
    description: Optional[str] = None
    direction: Optional[str] = None
    risk_type: Optional[str] = None


class TagOut(ORMBase):
    id: int
    name: str
    description: str
    is_builtin: bool
    direction: str
    risk_type: str
    created_at: datetime


# =====================================================================
# 检测能力
# =====================================================================
class ModelBase(BaseModel):
    name: str
    description: str = ""
    access_type: str = Field(..., description="rest 或 script")
    enabled: bool = True

    # REST 字段
    endpoint_url: str = ""
    http_method: str = "POST"
    headers: Dict[str, Any] = {}
    body_template: Dict[str, Any] = {}
    safe_status_code: Optional[int] = None
    safe_jsonpath: str = ""
    safe_expected_value: str = ""
    prompt_jsonpath: str = ""

    # 脚本字段
    script_content: str = ""

    # 关联标签 ID 列表
    tag_ids: List[int] = []


class ModelCreate(ModelBase):
    pass


class ModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    endpoint_url: Optional[str] = None
    http_method: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    body_template: Optional[Dict[str, Any]] = None
    safe_status_code: Optional[int] = None
    safe_jsonpath: Optional[str] = None
    safe_expected_value: Optional[str] = None
    prompt_jsonpath: Optional[str] = None
    script_content: Optional[str] = None
    tag_ids: Optional[List[int]] = None


class ModelOut(ORMBase):
    id: int
    name: str
    description: str
    access_type: str
    enabled: bool
    endpoint_url: str
    http_method: str
    headers: Dict[str, Any]
    body_template: Dict[str, Any]
    safe_status_code: Optional[int]
    safe_jsonpath: str
    safe_expected_value: str
    prompt_jsonpath: str
    script_content: str
    tags: List[TagOut] = []
    created_at: datetime
    updated_at: datetime


class ValidationResult(BaseModel):
    """连接/脚本有效性检测结果。"""

    ok: bool
    message: str
    detail: Optional[str] = None


# =====================================================================
# 策略编排
# =====================================================================
class StrategyBase(BaseModel):
    name: str
    description: str = ""
    tag_id: int
    enabled: bool = True
    rule_type: Literal["sequential", "random"] = Field(
        "sequential",
        description="调用规则：sequential（顺序检测）/ random（随机检测）",
    )
    max_wait_seconds: float = 60.0
    timeout_policy: str = Field("unsafe", description="safe 或 unsafe")
    model_ids: List[int] = []


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tag_id: Optional[int] = None
    enabled: Optional[bool] = None
    rule_type: Optional[Literal["sequential", "random"]] = None
    max_wait_seconds: Optional[float] = None
    timeout_policy: Optional[str] = None
    model_ids: Optional[List[int]] = None


class StrategyOut(ORMBase):
    id: int
    name: str
    description: str
    tag_id: int
    enabled: bool
    rule_type: str
    max_wait_seconds: float
    timeout_policy: str
    models: List[ModelOut] = []
    created_at: datetime
    updated_at: datetime


# =====================================================================
# 对外 API 路径
# =====================================================================
class ApiPathBase(BaseModel):
    name: str
    path: str
    description: str = ""
    enabled: bool = True
    api_key_id: Optional[int] = None
    # 有序的策略 ID 列表
    strategy_ids: List[int] = []


class ApiPathCreate(ApiPathBase):
    pass


class ApiPathUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    api_key_id: Optional[int] = None
    strategy_ids: Optional[List[int]] = None


class ApiPathOut(ORMBase):
    id: int
    name: str
    path: str
    description: str
    enabled: bool
    api_key_id: Optional[int]
    strategies: List[StrategyOut] = []
    created_at: datetime


# =====================================================================
# 对外检测接口（公开 API）
# =====================================================================
class GuardRequest(BaseModel):
    """对外检测请求。"""

    messages: str = Field(..., description="被检测的消息字符串（JSON 格式文本）")
    jsonpath: str = Field(
        "", description="从被检测消息提取检测内容的 JsonPath；为空时检测整个消息"
    )
    illegal_status_code: int = Field(
        200, description="检测结果为非法时希望返回的 HTTP 状态码"
    )


class GuardResponse(BaseModel):
    """对外检测响应。"""

    code: int = Field(..., description="业务码，成功检测为 200")
    risk_level: str = Field("LOW", description="安全风险等级，预留字段，当前固定 LOW")
    message: str = Field("", description="风险提示消息")
    risk_type: str = Field(
        "", description="风险类型：个人信息检测/偏离主题检测/越狱攻击检测/幻觉虚构检测/不当言论低俗内容检测/提及竞品/其他"
    )


# =====================================================================
# 可观测日志
# =====================================================================
class RequestLogOut(ORMBase):
    id: int
    api_path: str
    client_ip: str
    request_body: Dict[str, Any]
    response_body: Dict[str, Any]
    result: str
    risk_type: str
    business_code: int
    latency_ms: float
    safe_count: Optional[int] = None
    unsafe_count: Optional[int] = None
    created_at: datetime


class DetectionLogOut(ORMBase):
    id: int
    request_log_id: Optional[int]
    strategy_id: Optional[int]
    strategy_name: str
    model_id: Optional[int]
    model_name: str
    access_type: str
    request_detail: str
    response_detail: str
    result: str
    latency_ms: float
    created_at: datetime


class StatsSummary(BaseModel):
    """统计信息汇总（用于大屏与可观测）。"""

    total_requests: int
    safe_count: int
    unsafe_count: int
    avg_latency_ms: float
    model_count: int
    strategy_count: int
    api_path_count: int
    risk_type_distribution: Dict[str, int]
    recent_trend: List[Dict[str, Any]]
