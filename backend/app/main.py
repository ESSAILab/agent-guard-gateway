"""
AI智能体安全网关 - 后端服务入口。

集成各业务路由、跨域、数据库初始化、大屏实时事件 WebSocket。
启动后自动建表并写入内置标签与默认管理员。
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    api_keys,
    api_paths,
    auth,
    guard,
    models,
    observability,
    strategies,
    tags,
    users,
)
from app.core.config import settings
from app.core.init_db import init_db
from app.services.broadcaster import broadcaster


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库。"""
    init_db()
    yield


app = FastAPI(
    title="AI智能体安全网关 API",
    description=(
        "面向生产环境的大语言模型交互安全检测护栏。\n\n"
        "提供检测模型管理、检测策略（顺序检测/随机检测）、对外检测 API、"
        "可观测与大屏展示等能力，方便被 AI 应用集成。"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # 禁用默认文档路由，在 SPA 静态文件挂载后手动注册
    redoc_url=None,
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 业务路由注册
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(api_keys.router)
app.include_router(tags.router)
app.include_router(models.router)
app.include_router(strategies.router)
app.include_router(api_paths.router)
app.include_router(observability.router)
# 对外检测网关（公开，使用 API Key 认证）
app.include_router(guard.router)


@app.get("/api/health", tags=["系统"], summary="健康检查")
def health():
    """健康检查接口，供部署探针使用。"""
    return {"status": "ok", "service": "ai-guardrail"}


@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    """大屏实时事件推送通道。"""
    await broadcaster.connect(ws)
    try:
        while True:
            # 保持连接；忽略客户端消息内容
            await ws.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(ws)
    except Exception:
        await broadcaster.disconnect(ws)


# ---------------------------------------------------------------------
# API 文档路由（始终可用）
# ---------------------------------------------------------------------

# 文档静态资源本地路径
_DOCS_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static", "docs")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        swagger_js_url="/static/docs/swagger-ui-bundle.min.js",
        swagger_css_url="/static/docs/swagger-ui.min.css",
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/docs/redoc.standalone.min.js",
    )


# 挂载文档静态资源
if os.path.isdir(_DOCS_STATIC_DIR):
    app.mount("/static/docs", StaticFiles(directory=_DOCS_STATIC_DIR), name="docs-static")


# ---------------------------------------------------------------------
# 静态前端托管（生产单镜像部署）
# 若存在已构建的前端产物目录，则挂载为根路径的 SPA。
# 开发模式下前端由 Vite 独立提供，本段不影响。
# ---------------------------------------------------------------------

_FRONTEND_DIST = os.environ.get(
    "FRONTEND_DIST",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),
)

_FRONTEND_ASSETS = os.path.join(_FRONTEND_DIST, "assets")
if os.path.isdir(_FRONTEND_DIST) and os.path.isdir(_FRONTEND_ASSETS):
    # 静态资源（js/css 等）
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_ASSETS),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """前端使用 Hash 路由，未匹配的非 API 路径回退到 index.html。"""
        candidate = os.path.join(_FRONTEND_DIST, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
