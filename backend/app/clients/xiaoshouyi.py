"""
销售易（XiaoShouYi）服务工单接口客户端。

- 鉴权：OAuth2 password grant → Bearer token（自动缓存、过期前刷新）
- 新增工单：POST /openapi/insertServiceCase

Reference: docs/销售易服务工单接口文档.md
"""
import asyncio
import calendar
import logging
import time
from datetime import datetime as dt
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Token 提前刷新阈值（秒），提前 5 分钟刷新避免边界竞争
_TOKEN_REFRESH_MARGIN = 300

# API 文档中标注为"年月日时间戳"的字段（需从日期字符串转为 Unix 时间戳）
_TIMESTAMP_FIELDS = {
    "serviceCycleStart__c",
    "serviceCycleEnd__c",
    "planFeedbackTime__c",
    "requireSolveTime__c",
}

# 可重试的 HTTP 状态码
_RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}

# 可重试的网络异常类型
_RETRYABLE_NETWORK_ERRORS = (
    httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout,
    httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.PoolTimeout,
)


class XiaoShouYiError(RuntimeError):
    """销售易 API 错误，携带可重试标记供调用方决策。"""
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


# API 文档明确要求的必填字段（独立于 field_config.yaml 的 UI 校验标记）
_API_DOC_REQUIRED_FIELDS: set[str] = {
    "ownerId", "dimDepart", "entityType", "name",
    "caseAccountId", "projectName__c",
    "problemResponsible__c", "problemDept__c",
}


def _load_required_fields() -> set[str]:
    """加载 to_api_body() 始终发送的字段集合。

    取 field_config.yaml 的 required_keys（UI 层必填）与 API 文档必填字段的
    并集，确保任何一方标记为必填的字段都不会被 to_api_body() 过滤掉。
    """
    try:
        from app.core.field_config import load_field_config
        yaml_required = load_field_config().required_keys
        return yaml_required | _API_DOC_REQUIRED_FIELDS
    except Exception:
        logger.warning("无法加载 field_config，使用 API 文档必填字段集合")
        return _API_DOC_REQUIRED_FIELDS


_REQUIRED_FIELDS: set[str] = _load_required_fields()


def _normalize_timestamp(value: str) -> str:
    """将日期字符串转为 Unix 时间戳字符串。

    销售易 API 的"年月日时间戳"字段期望 Unix epoch 秒数（如 "1784797500"），
    但 v_ticket 视图中可能存储 YYYY-MM-DD 格式字符串，此处做兼容转换。
    如果已经是纯数字时间戳则原样返回。
    """
    if not value or not value.strip():
        return ""
    value = value.strip()
    # 已经是纯数字时间戳，直接返回
    if value.isdigit():
        return value
    # 尝试解析为日期字符串 → 转为时间戳（当天 00:00:00 UTC）
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
        try:
            d = dt.strptime(value, fmt)
            return str(calendar.timegm(d.utctimetuple()))
        except ValueError:
            continue
    logger.warning("无法解析时间戳字段值 %r，原样发送", value)
    return value


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
        """转为 API JSON body。

        - 所有已知字段始终发送（空值发空字符串），避免 API 因缺少字段而 NPE
        - 时间戳字段自动从日期字符串转为 Unix 时间戳
        - idempotency_key 以 idempotencyKey__c 自定义字段发送（__c 后缀
          符合销售易 Salesforce 风格 API 约定）
        """
        data: dict[str, Any] = {"defectFlag__c": self.defectFlag__c}

        # 幂等键以自定义字段发送
        if self.idempotency_key:
            data["idempotencyKey__c"] = self.idempotency_key

        for field_name in self.model_fields:
            if field_name in ("defectFlag__c", "idempotency_key"):
                continue
            value = getattr(self, field_name)

            if value is None:
                value = ""

            # 所有字段始终发送，空值发空字符串
            # （销售易 API 开发中，健壮性不足，字段缺失比空字符串更危险）
            # 时间戳字段：自动将日期字符串转为 Unix 时间戳
            if field_name in _TIMESTAMP_FIELDS and value != "":
                value = _normalize_timestamp(value)
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

        # 共享 HTTP 客户端（延迟创建，复用连接池）
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """延迟创建共享 httpx 客户端，复用连接池减少 TCP/TLS 握手开销。"""
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=None)  # 超时由调用方 asyncio.wait_for 控制
        return self._http

    async def close(self) -> None:
        """关闭 HTTP 客户端连接池。"""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

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

        http = await self._get_client()
        try:
            resp = await http.post(
                self._token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except _RETRYABLE_NETWORK_ERRORS as e:
            raise XiaoShouYiError(f"销售易 token 网络错误: {e}", retryable=True) from e

        if resp.status_code >= 400:
            retryable = resp.status_code in _RETRYABLE_HTTP_STATUS
            raise XiaoShouYiError(
                f"销售易 token HTTP {resp.status_code}", retryable=retryable,
            )

        data = resp.json()
        access_token = data.get("access_token", "")
        expires_in = data.get("expires_in", 86400)

        if not access_token:
            raise XiaoShouYiError(
                f"销售易 token 响应中缺少 access_token: {data}", retryable=True,
            )

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

        t0 = time.monotonic()
        logger.info("销售易 create_work_order → %s", url)
        logger.debug("request body: %s", body)

        http = await self._get_client()
        try:
            resp = await http.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
        except _RETRYABLE_NETWORK_ERRORS as e:
            raise XiaoShouYiError(f"销售易网络错误: {e}", retryable=True) from e

        elapsed_ms = round((time.monotonic() - t0) * 1000)

        # 解析响应体：尝试 JSON，失败则保留原始文本用于排查
        try:
            raw = resp.json()
        except Exception:
            raw = {"_body": resp.text[:500]}

        # 实际 API 响应格式: {"code": 200, "message": "成功", "data": {"code": 2000001, "dataId": ..., "success": true}}
        # 文档中描述为:    {"code": "200", "msg": "OK", "data": {"id": ..., "objectApiKey": "serviceCase"}}
        # 两者有差异，此处兼容实际 API 格式
        code = raw.get("code", "")
        msg = raw.get("message") or raw.get("msg", "")

        if resp.status_code >= 400 or str(code) != "200":
            logger.error(
                "销售易 create_work_order 失败: status=%d code=%s msg=%s duration_ms=%d body=%s",
                resp.status_code, code, msg, elapsed_ms, raw,
            )
            retryable = resp.status_code in _RETRYABLE_HTTP_STATUS
            raise XiaoShouYiError(
                f"销售易同步失败 [{code}]: {msg}", retryable=retryable,
            )

        # 实际 API 返回的外部 ID 在 data.dataId（大整数），文档中为 data.id
        data_block = raw.get("data", {})
        external_id = data_block.get("dataId") or data_block.get("id")
        if isinstance(external_id, (int,)):
            external_id = str(external_id)

        logger.info(
            "销售易 create_work_order 成功: external_id=%s duration_ms=%d status=%d",
            external_id, elapsed_ms, resp.status_code,
        )
        return CreateWorkOrderResponse(external_id=str(external_id) if external_id else None, raw=raw)


# ---------------------------------------------------------------------------
# Factory（进程级单例）
# ---------------------------------------------------------------------------

_client_instance: XiaoShouYiClient | None = None


def get_xiaoshouyi_client() -> XiaoShouYiClient:
    """获取进程级单例客户端。

    共享 httpx 连接池 + token 缓存，避免每次同步新建客户端（连接池
    不复用、token 每单重取，导致每次同步 2 次 HTTP 往返）。仅在应用
    shutdown 时通过 close_xiaoshouyi_client() 关闭。
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = XiaoShouYiClient()
    return _client_instance


async def close_xiaoshouyi_client() -> None:
    """关闭单例客户端（应用优雅关闭时调用）。"""
    global _client_instance
    if _client_instance is not None:
        await _client_instance.close()
        _client_instance = None
