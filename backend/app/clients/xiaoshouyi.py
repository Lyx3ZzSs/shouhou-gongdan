"""
销售易（XiaoShouYi）服务工单接口客户端。

- 鉴权：OAuth2 password grant → Bearer token（自动缓存、过期前刷新）
- 新增工单：POST /openapi/insertServiceCase

Reference: docs/销售易服务工单接口文档.md
"""
import asyncio
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Token 提前刷新阈值（秒），提前 5 分钟刷新避免边界竞争
_TOKEN_REFRESH_MARGIN = 300


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateWorkOrderRequest(BaseModel):
    """销售易 insertServiceCase 请求体 — 33 可见字段 + defectFlag__c + idempotency_key。"""
    # ---- Idempotency ----
    idempotency_key: str = ""

    # ---- Required ----
    ownerId: str = ""
    dimDepart: str = ""
    entityType: str = "11010045500001"
    name: str = ""
    caseSource: str = ""
    feedbackChannel__c: str = ""
    workOrderStatus__c: str = ""
    caseDescription: str = ""
    caseStatus: str = ""

    # ---- Optional ----
    caseAccountId: str = ""
    custLevel1__c: str = ""
    projectName__c: str = ""
    projectProvince__c: str = ""
    bigCustShortName__c: str = ""
    serviceCycleStart__c: str = ""
    serviceCycleEnd__c: str = ""
    isOfflineApply__c: str = ""
    isOverdueService__c: str = ""
    problemLevel__c: str = ""
    problemType1__c: str = ""
    problemType2__c: str = ""
    problemType3__c: str = ""
    feedbackCount__c: str = ""
    problemResponsible__c: str = ""
    problemDept__c: str = ""
    feedbackUserName__c: str = ""
    feedbackUserContact__c: str = ""
    needCallBack__c: str = ""
    isHandled__c: str = ""
    needOnSite__c: str = ""
    remark__c: str = ""
    planFeedbackTime__c: str = ""
    requireSolveTime__c: str = ""
    relatedAttachment__c: str = ""
    defectFlag__c: str = "1"

    def to_api_body(self) -> dict[str, Any]:
        """转为 API JSON body，空字符串的 optional 字段会被排除。

        idempotency_key 以 idempotencyKey__c 自定义字段发送（__c 后缀符合
        销售易 Salesforce 风格 API 约定）。注意：销售易是否支持此字段去重尚
        未确认，当前属于尽力而为；真正的幂等保证来自本地原子认领机制。
        """
        data: dict[str, Any] = {"defectFlag__c": self.defectFlag__c}

        # 幂等键以自定义字段发送（尽力而为，依赖销售易端支持）
        if self.idempotency_key:
            data["idempotencyKey__c"] = self.idempotency_key

        for field_name, field_info in self.model_fields.items():
            if field_name in ("defectFlag__c", "idempotency_key"):
                continue
            value = getattr(self, field_name)
            if value != "" and value is not None:
                data[field_name] = value

        return data


# ---------------------------------------------------------------------------
# DB → 销售易 API 字段映射
# ---------------------------------------------------------------------------

# DB 列名（v_ticket 视图驼峰命名）→ 销售易 API 字段名（完全一致时省略映射）
DB_TO_API_FIELD_MAP: dict[str, str] = {
    "ownerId":                "ownerId",
    "dimDepart":              "dimDepart",
    "entityType":             "entityType",
    "name":                   "name",
    "caseSource":             "caseSource",
    "feedbackChannel__c":     "feedbackChannel__c",
    "workOrderStatus__c":     "workOrderStatus__c",
    "caseDescription":        "caseDescription",
    "caseStatus":             "caseStatus",
    "caseAccountId":          "caseAccountId",
    "custLevel1__c":          "custLevel1__c",
    "projectName__c":         "projectName__c",
    "projectProvince__c":     "projectProvince__c",
    "bigCustShortName__c":    "bigCustShortName__c",
    "serviceCycleStart__c":   "serviceCycleStart__c",
    "serviceCycleEnd__c":     "serviceCycleEnd__c",
    "isOfflineApply__c":      "isOfflineApply__c",
    "isOverdueService__c":    "isOverdueService__c",
    "problemLevel__c":        "problemLevel__c",
    "problemType1__c":        "problemType1__c",
    "problemType2__c":        "problemType2__c",
    "problemType3__c":        "problemType3__c",
    "feedbackCount__c":       "feedbackCount__c",
    "problemResponsible__c":  "problemResponsible__c",
    "problemDept__c":         "problemDept__c",
    "feedbackUserName__c":    "feedbackUserName__c",
    "feedbackUserContact__c": "feedbackUserContact__c",
    "needCallBack__c":        "needCallBack__c",
    "isHandled__c":           "isHandled__c",
    "needOnSite__c":          "needOnSite__c",
    "remark__c":              "remark__c",
    "relatedAttachment__c":   "relatedAttachment__c",
    "planFeedbackTime__c":    "planFeedbackTime__c",
    "requireSolveTime__c":    "requireSolveTime__c",
    "defectFlag__c":          "defectFlag__c",
}


def map_db_to_xiaoshouyi(
    merged: dict[str, object],
    idempotency_key: str = "",
) -> CreateWorkOrderRequest:
    """将 merge(v_ticket, field_overrides) 的结果映射为销售易 API 请求。"""
    return CreateWorkOrderRequest(
        idempotency_key=idempotency_key,
        **{
            api_key: str(merged.get(db_key, "")) if merged.get(db_key) is not None else ""
            for db_key, api_key in DB_TO_API_FIELD_MAP.items()
        }
    )


class CreateWorkOrderResponse(BaseModel):
    """销售易返回的工单创建结果。"""
    external_id: str | None = None
    raw: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class XiaoShouYiClient:
    """销售易 API 客户端（OAuth2 + 服务工单新增）。

    Usage:
        client = get_xiaoshouyi_client()
        resp = await client.create_work_order(CreateWorkOrderRequest(...))
    """

    def __init__(self) -> None:
        from app.core.config import settings

        self._base_url = settings.XIAOSHOUYI_BASE_URL.rstrip("/") if settings.XIAOSHOUYI_BASE_URL else ""
        self._token_url = settings.XIAOSHOUYI_TOKEN_URL
        self._client_id = settings.XIAOSHOUYI_CLIENT_ID
        self._client_secret = settings.XIAOSHOUYI_CLIENT_SECRET.get_secret_value()
        self._redirect_uri = settings.XIAOSHOUYI_REDIRECT_URI
        self._username = settings.XIAOSHOUYI_USERNAME
        self._password = settings.XIAOSHOUYI_PASSWORD.get_secret_value()

        # Token 缓存
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _acquire_token(self) -> str:
        """通过 OAuth2 password grant 获取 access_token。

        POST https://login.xiaoshouyi.com/auc/oauth2/token
        Content-Type: application/x-www-form-urlencoded
        """
        logger.info("销售易 token 获取中...")

        payload = {
            "grant_type": "password",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "username": self._username,
            "password": self._password,
        }

        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(
                self._token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

        access_token = data.get("access_token", "")
        expires_in = data.get("expires_in", 86400)

        if not access_token:
            raise RuntimeError(f"销售易 token 响应中缺少 access_token: {data}")

        self._access_token = access_token
        self._token_expires_at = time.time() + expires_in

        logger.info("销售易 token 获取成功 (expires_in=%ds)", expires_in)
        return access_token

    async def _get_token(self) -> str:
        """获取有效 token，必要时自动刷新。"""
        now = time.time()
        if self._access_token and (self._token_expires_at - now > _TOKEN_REFRESH_MARGIN):
            return self._access_token

        async with self._token_lock:
            # Double-check：可能在等锁时已被其他协程刷新
            now2 = time.time()
            if self._access_token and (self._token_expires_at - now2 > _TOKEN_REFRESH_MARGIN):
                return self._access_token
            return await self._acquire_token()

    # ------------------------------------------------------------------
    # Business API
    # ------------------------------------------------------------------

    async def create_work_order(
        self, data: CreateWorkOrderRequest,
    ) -> CreateWorkOrderResponse:
        """调用销售易服务工单新增接口。

        POST {base_url}/openapi/insertServiceCase
        Authorization: Bearer {access_token}
        """
        if not self._base_url:
            logger.warning("销售易 XIAOSHOUYI_BASE_URL 未配置，跳过同步")
            return CreateWorkOrderResponse(external_id=None)

        token = await self._get_token()
        url = f"{self._base_url}/openapi/insertServiceCase"
        body = data.to_api_body()

        logger.info("销售易 create_work_order → %s", url)
        logger.debug("request body: %s", body)

        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )

        raw = resp.json() if resp.status_code < 500 else {}
        code = raw.get("code", "")
        msg = raw.get("msg", "")

        if resp.status_code >= 400 or code != "200":
            logger.error(
                "销售易 create_work_order 失败: status=%d code=%s msg=%s body=%s",
                resp.status_code, code, msg, raw,
            )
            raise RuntimeError(f"销售易同步失败 [{code}]: {msg}")

        external_id = raw.get("data", {}).get("id")
        if isinstance(external_id, (int,)):
            external_id = str(external_id)

        logger.info(
            "销售易 create_work_order 成功: external_id=%s objectApiKey=%s",
            external_id,
            raw.get("data", {}).get("objectApiKey", ""),
        )
        return CreateWorkOrderResponse(external_id=str(external_id) if external_id else None, raw=raw)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_xiaoshouyi_client() -> XiaoShouYiClient:
    """工厂函数：创建销售易客户端实例。"""
    return XiaoShouYiClient()
