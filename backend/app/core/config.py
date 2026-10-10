"""
应用配置模块。

使用 pydantic-settings 从环境变量 / .env 文件加载配置。
所有配置项均提供合理默认值，便于本地零配置启动。
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。字段名大小写不敏感，自动从环境变量读取。"""

    # 读取同目录下的 .env 文件；忽略未声明的额外变量
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- 服务监听 ----
    GATEWAY_HOST: str = "0.0.0.0"
    GATEWAY_PORT: int = 8000

    # ---- 数据库 ----
    DATABASE_URL: str = "sqlite:///./guardrail.db"

    # ---- 认证 ----
    SECRET_KEY: str = "please-change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # ---- 默认管理员 ----
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # ---- 可观测 ----
    # debug / basic / statistics
    OBSERVABILITY_LEVEL: str = "basic"

    # ---- 跨域 ----
    CORS_ORIGINS: str = "*"

    @property
    def cors_origin_list(self) -> List[str]:
        """将逗号分隔的来源串解析为列表。"""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """返回全局唯一的配置实例（带缓存）。"""
    return Settings()


settings = get_settings()
