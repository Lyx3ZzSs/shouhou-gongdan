import os
import warnings

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    JWT_SECRET: str = "dev-secret-change-in-production"
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:YOUR_DB_PASSWORD@localhost:5432/shouhou_gongdan"

    # 销售易（XiaoShouYi）服务工单接口
    XIAOSHOUYI_BASE_URL: str = ""
    XIAOSHOUYI_API_KEY: str = ""

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "dev-secret-change-in-production":
            if os.getenv("ENV", "") in ("production", "prod"):
                raise ValueError(
                    "JWT_SECRET 不能使用默认值，请设置环境变量 JWT_SECRET"
                )
            warnings.warn(
                "JWT_SECRET 使用默认值，生产环境请务必修改！",
                UserWarning,
                stacklevel=2,
            )
        if len(v) < 32:
            if os.getenv("ENV", "") in ("production", "prod"):
                raise ValueError(
                    "JWT_SECRET 长度不足 32 字符，生产环境请使用更强的密钥"
                )
            warnings.warn(
                "JWT_SECRET 长度不足 32 字符，建议使用更长的密钥",
                UserWarning,
                stacklevel=2,
            )
        return v


settings = Settings()
