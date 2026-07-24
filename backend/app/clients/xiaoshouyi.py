"""
销售易（XiaoShouYi）服务工单接口客户端。

- 鉴权：OAuth2 password grant → Bearer token（自动缓存、过期前刷新）
- 新增工单：POST /openapi/insertServiceCase

Reference: docs/销售易服务工单接口文档.md
"""
from __future__ import annotations

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
    """销售易 insertServiceCase 请求体 — 33 可见字段 + defectFlag__c。"""
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
        """转为 API JSON body，空字符串的 optional 字段会被排除。"""
        data: dict[str, Any] = {"defectFlag__c": self.defectFlag__c}

        for field_name, field_info in self.model_fields.items():
            if field_name == "defectFlag__c":
                continue
            value = getattr(self, field_name)
            if value != "" and value is not None:
                data[field_name] = value

        return data


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
        self._client_secret = settings.XIAOSHOUYI_CLIENT_SECRET
        self._redirect_uri = settings.XIAOSHOUYI_REDIRECT_URI
        self._username = settings.XIAOSHOUYI_USERNAME
        self._password = settings.XIAOSHOUYI_PASSWORD

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
