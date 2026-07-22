import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Keycloak OIDC
    KEYCLOAK_ISSUER: str = ""
    KEYCLOAK_JWKS_URL: str = ""
    KEYCLOAK_AUDIENCE: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = ""

    # 销售易（XiaoShouYi）服务工单接口
    XIAOSHOUYI_BASE_URL: str = ""
    XIAOSHOUYI_API_KEY: str = ""


settings = Settings()
