"""
销售易（XiaoShouYi）服务工单新增接口客户端。

当前为抽象层占位，具体 HTTP 实现待销售易 API 文档明确后补充。
"""

import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CreateWorkOrderRequest(BaseModel):
    """销售易服务工单创建请求体。字段待销售易文档明确后补充。"""
    idempotency_key: str
    # TODO: 补充工单字段映射（站点、项目、分类、描述等 28 个字段）


class CreateWorkOrderResponse(BaseModel):
    """销售易返回的工单创建结果。"""
    external_id: str | None = None


class XiaoShouYiClient:
    """销售易 API 客户端。

    Usage:
        client = XiaoShouYiClient(
            base_url=settings.XIAOSHOUYI_BASE_URL,
            api_key=settings.XIAOSHOUYI_API_KEY,
        )
        resp = await client.create_work_order(request)
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def create_work_order(
        self, data: CreateWorkOrderRequest,
    ) -> CreateWorkOrderResponse:
        """调用销售易服务工单新增接口。

        当前为占位实现，待 API 文档明确后替换为真实 HTTP 调用。
        """
        if not self.base_url:
            logger.warning("销售易 base_url 未配置，跳过同步")
            return CreateWorkOrderResponse(external_id=None)

        # TODO: 实现真实 HTTP 调用
        # async with httpx.AsyncClient() as client:
        #     resp = await client.post(
        #         f"{self.base_url}/api/v1/workorders",
        #         json=data.model_dump(),
        #         headers={"Authorization": f"Bearer {self.api_key}"},
        #     )
        #     resp.raise_for_status()
        #     return CreateWorkOrderResponse(**resp.json())

        raise NotImplementedError(
            "销售易 create_work_order 尚未实现，请补充 HTTP 调用逻辑"
        )


def get_xiaoshouyi_client() -> XiaoShouYiClient:
    """工厂函数：从配置创建销售易客户端单例。"""
    from app.core.config import settings
    return XiaoShouYiClient(
        base_url=settings.XIAOSHOUYI_BASE_URL,
        api_key=settings.XIAOSHOUYI_API_KEY,
    )
