from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # 认证开关：false 时跳过 Keycloak 校验，使用默认开发用户
    AUTH_ENABLED: bool = True

    # Keycloak OIDC
    KEYCLOAK_ISSUER: str = ""
    KEYCLOAK_JWKS_URL: str = ""
    KEYCLOAK_AUDIENCE: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = ""

    # 销售易（XiaoShouYi）服务工单接口
    XIAOSHOUYI_TOKEN_URL: str = "https://login.xiaoshouyi.com/auc/oauth2/token"
    XIAOSHOUYI_BASE_URL: str = ""
    XIAOSHOUYI_CLIENT_ID: str = ""
    XIAOSHOUYI_CLIENT_SECRET: SecretStr = SecretStr("")
    XIAOSHOUYI_REDIRECT_URI: str = "https://api-tencent.xiaoshouyi.com"
    XIAOSHOUYI_USERNAME: str = ""
    XIAOSHOUYI_PASSWORD: SecretStr = SecretStr("")
    XIAOSHOUYI_SYNC_MAX_RETRIES: int = 3
    XIAOSHOUYI_SYNC_TIMEOUT_SECONDS: float = 20.0
    XIAOSHOUYI_SYNC_MAX_CONCURRENCY: int = 5
    # 周期扫描孤儿/滞留同步记录的间隔（秒）；0 表示禁用
    XIAOSHOUYI_SWEEP_INTERVAL_SECONDS: float = 120.0
    # 单次周期扫描最多恢复的记录数，防止积压时无界 fan-out
    XIAOSHOUYI_SWEEP_MAX_PER_CYCLE: int = 50


settings = Settings()
