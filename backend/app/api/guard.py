"""
对外检测网关接口（供 AI 应用集成调用）。

通过统一入口 POST /guard{path} 匹配已配置且生效的 API 路径，
校验 API Key 后执行策略链检测，返回护栏检测结果。
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ApiKey, ApiPath
from app.schemas import GuardRequest, GuardResponse
from app.services.gateway import run_detection

router = APIRouter(prefix="/guard", tags=["对外检测接口"])


def _check_api_key(db: Session, api_path: ApiPath, provided_key: str | None) -> None:
    """校验该路径所需的 API Key。"""
    if not api_path.api_key_id:
        # 未绑定 Key 的路径视为开放（不建议用于生产）
        return
    key = db.query(ApiKey).filter(ApiKey.id == api_path.api_key_id).first()
    if not key or not key.enabled:
        raise HTTPException(status_code=403, detail="该路径绑定的 API Key 不可用")
    if not provided_key or provided_key != key.key_value:
        raise HTTPException(
            status_code=401, detail="API Key 无效，请在 X-API-Key 头中提供正确的密钥"
        )


@router.post(
    "{full_path:path}",
    response_model=GuardResponse,
    summary="执行安全检测",
    description=(
        "对外检测入口。`full_path` 为在「检测场景」中配置的对外路径，"
        "例如配置路径为 /chat-input，则调用 POST /guard/chat-input。\n\n"
        "请求头需携带 `X-API-Key`（当该路径绑定了认证密钥时）。"
    ),
)
async def guard_detect(
    full_path: str,
    payload: GuardRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    # 1) 匹配已配置的对外路径
    target = "/" + full_path.lstrip("/")
    api_path = db.query(ApiPath).filter(ApiPath.path == target).first()
    if not api_path:
        raise HTTPException(status_code=404, detail="未找到对应的检测路径配置")
    if not api_path.enabled:
        raise HTTPException(status_code=403, detail="该检测路径未生效")

    # 2) API Key 认证
    _check_api_key(db, api_path, x_api_key)

    # 3) 执行检测
    client_ip = request.client.host if request.client else ""
    result = await run_detection(db, api_path, payload, client_ip)

    # 4) 当检测为非法时，按调用方指定的状态码返回（默认 200）
    if result.code != 200 and payload.illegal_status_code:
        response.status_code = payload.illegal_status_code
    return result
