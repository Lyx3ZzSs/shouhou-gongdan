"""实证测试销售易 idempotencyKey__c 去重语义。

同一 key 连续调用 3 次 insertServiceCase：
  1. key=K, body=A            → dataId1
  2. key=K, body=A（完全一致） → dataId2
  3. key=K, body=B（name 不同）→ dataId3

判定：
  - dataId1==dataId2==dataId3 → 按 key 去重（顺序重试安全）
  - dataId1==dataId2!=dataId3 → 按请求内容精确去重（同 key 同 body 安全）
  - dataId1!=dataId2          → 完全不去重（顺序重试会重复建单，需对账机制）

Usage: cd backend && .venv/bin/python scripts/test_idempotency_key.py
"""
import asyncio
import uuid

from app.clients.xiaoshouyi import get_xiaoshouyi_client, CreateWorkOrderRequest
from app.core.config import settings

# 基于已验证可用的联调请求模板（problemResponsible__c 用 101633 避免 NPE）
BASE = {
    "ownerId": "101633",
    "dimDepart": "sprixin",
    "entityType": "11010045500001",
    "name": "幂等测试-工单A",
    "caseSource": "1",
    "feedbackChannel__c": "1",
    "workOrderStatus__c": "1",
    "caseDescription": "幂等去重语义实证测试工单。",
    "caseStatus": "1",
    "caseAccountId": "SPCZ202408210132",
    "custLevel1__c": "1",
    "projectName__c": "XSJH20260723012",
    "projectProvince__c": "北京市",
    "bigCustShortName__c": "测试大客户",
    "serviceCycleStart__c": "1784797500",
    "serviceCycleEnd__c": "1784797500",
    "isOfflineApply__c": "1",
    "isOverdueService__c": "1",
    "problemLevel__c": "1",
    "problemType1__c": "1",
    "problemType2__c": "1",
    "problemType3__c": "1",
    "feedbackCount__c": "1",
    "problemResponsible__c": "101633",
    "problemDept__c": "sprixin",
    "feedbackUserName__c": "测试用户",
    "feedbackUserContact__c": "13800138000",
    "needCallBack__c": "1",
    "isHandled__c": "1",
    "needOnSite__c": "1",
    "remark__c": "幂等测试备注",
    "planFeedbackTime__c": "1784797500",
    "requireSolveTime__c": "1784797500",
    "defectFlag__c": "1",
}


def _req(key: str, name: str, remark: str) -> CreateWorkOrderRequest:
    body = dict(BASE)
    body["name"] = name
    body["remark__c"] = remark
    return CreateWorkOrderRequest(idempotency_key=key, **body)


async def main():
    if not settings.XIAOSHOUYI_BASE_URL:
        print("❌ XIAOSHOUYI_BASE_URL 未配置，无法测试")
        return

    client = get_xiaoshouyi_client()
    key = f"idem-verify-{uuid.uuid4().hex[:10]}"
    print(f"测试 key: {key}\n")

    results = []
    for i, (name, remark) in enumerate([
        ("幂等测试-工单A", "第一次调用"),
        ("幂等测试-工单A", "第一次调用"),   # 与第一次完全一致
        ("幂等测试-工单B", "第三次调用，name 已改"),  # 同 key 异 body
    ], start=1):
        resp = await client.create_work_order(_req(key, name, remark))
        results.append(resp.external_id)
        print(f"  调用 {i}: name={name!r} remark={remark!r} → dataId={resp.external_id}")

    d1, d2, d3 = results
    print("\n" + "=" * 60)
    if d1 == d2 == d3:
        print("判定: ✅ 销售易按 idempotencyKey__c 去重（同 key 即使内容不同也返回原 dataId）")
        print("含义: 顺序重试（超时后同 key 重发）安全，不会重复建单。")
    elif d1 == d2 and d2 != d3:
        print("判定: ⚠️ 销售易按请求内容精确去重（同 key+同 body 才返回原 dataId）")
        print("含义: 我们的重试发送同 key+同 body，顺序重试安全；但同 key 异 body 会新建。")
    elif d1 != d2:
        print("判定: ❌ 销售易不去重（同 key+同 body 也新建）")
        print("含义: 顺序重试会重复建单，需引入对账机制（按 name/时间戳回查）。")
    else:
        print(f"判定: 结果异常 d1={d1} d2={d2} d3={d3}，请人工核对")
    print("=" * 60)

    await client.close()


asyncio.run(main())
