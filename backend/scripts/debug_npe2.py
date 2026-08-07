"""字段排查 Round 2：隔离 caseAccountId 和 projectName__c。"""
import asyncio, json, httpx
from app.core.config import settings

async def get_token():
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(
            settings.XIAOSHOUYI_TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": settings.XIAOSHOUYI_CLIENT_ID,
                "client_secret": settings.XIAOSHOUYI_CLIENT_SECRET.get_secret_value(),
                "redirect_uri": settings.XIAOSHOUYI_REDIRECT_URI,
                "username": settings.XIAOSHOUYI_USERNAME,
                "password": settings.XIAOSHOUYI_PASSWORD.get_secret_value(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return resp.json()["access_token"]

async def test(label, body):
    token = await get_token()
    url = f'{settings.XIAOSHOUYI_BASE_URL}/openapi/insertServiceCase'
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(url, json=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        })
        raw = resp.json()
        code = raw.get("code")
        ok = resp.status_code == 200 and str(code) == "200"
        data_block = raw.get("data") or {}
        data_id = data_block.get("dataId", "")
        msg = raw.get("message", "")[:80]
        print(f"{label}: {'OK' if ok else 'FAIL'} code={code} dataId={data_id} msg={msg}")
        return ok

async def main():
    # SAMPLE 模板（已验证成功）
    SAMPLE = {
        "ownerId": "101633", "dimDepart": "sprixin", "entityType": "11010045500001",
        "name": "排查2", "caseSource": "1", "feedbackChannel__c": "1",
        "workOrderStatus__c": "1", "caseDescription": "排查",
        "caseStatus": "1", "caseAccountId": "SPCZ202408210132",
        "custLevel1__c": "1", "projectName__c": "XSJH20260723012",
        "projectProvince__c": "北京市", "bigCustShortName__c": "测试大客户",
        "serviceCycleStart__c": "1784797500", "serviceCycleEnd__c": "1784797500",
        "isOfflineApply__c": "1", "isOverdueService__c": "1",
        "problemLevel__c": "1", "problemType1__c": "1", "problemType2__c": "1",
        "problemType3__c": "1", "feedbackCount__c": "1",
        "problemResponsible__c": "101633", "problemDept__c": "sprixin",
        "feedbackUserName__c": "测试", "feedbackUserContact__c": "13800138000",
        "needCallBack__c": "1", "isHandled__c": "1", "needOnSite__c": "1",
        "remark__c": "测试", "planFeedbackTime__c": "1784797500",
        "requireSolveTime__c": "1784797500", "defectFlag__c": "1",
    }

    user_vals = {
        "ownerId": "101634", "name": "售后单",
        "caseSource": "6", "feedbackChannel__c": "6", "workOrderStatus__c": "3",
        "caseDescription": "测试描述", "caseStatus": "2", "problemLevel__c": "2",
        "problemType3__c": "89",
        "problemResponsible__c": "100658", "problemDept__c": "576825",
        "feedbackUserName__c": "向逸辉",
        "needCallBack__c": "1", "isHandled__c": "2", "needOnSite__c": "2",
        "remark__c": "1", "isOfflineApply__c": "2", "isOverdueService__c": "2",
    }

    # 测试: 只替换业务字段，保留 SAMPLE 的 caseAccountId 和 projectName__c
    await test("1.仅业务字段", {**SAMPLE, **user_vals})

    # 测试: 只替换 caseAccountId
    await test("2.仅caseAccountId", {**SAMPLE, "caseAccountId": "CZ1000001"})

    # 测试: 只替换 projectName__c
    await test("3.仅projectName", {**SAMPLE, "projectName__c": "XSJH20260528003"})

    # 测试: 只替换 problemResponsible__c
    await test("4.仅problemResp", {**SAMPLE, "problemResponsible__c": "100658"})

    # 测试: 只替换 problemDept__c
    await test("5.仅problemDept", {**SAMPLE, "problemDept__c": "576825"})

    # 测试: 替换四个关联字段
    await test("6.四个关联字段", {**SAMPLE,
        "caseAccountId": "CZ1000001", "projectName__c": "XSJH20260528003",
        "problemResponsible__c": "100658", "problemDept__c": "576825",
    })

asyncio.run(main())
