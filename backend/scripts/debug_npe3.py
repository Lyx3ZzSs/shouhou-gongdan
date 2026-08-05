"""字段排查 Round 3：确认 problemResponsible 是唯一 NPE 根因，排查其他字段。"""
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
    SAMPLE = {
        "ownerId": "101633", "dimDepart": "sprixin", "entityType": "11010045500001",
        "name": "排查3", "caseSource": "1", "feedbackChannel__c": "1",
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

    # 逐个确认其他用户字段
    await test("1.ownerId=101634", {**SAMPLE, "ownerId": "101634"})
    await test("2.caseSource=6", {**SAMPLE, "caseSource": "6"})
    await test("3.feedbackChannel=6", {**SAMPLE, "feedbackChannel__c": "6"})
    await test("4.workOrderStatus=3", {**SAMPLE, "workOrderStatus__c": "3"})
    await test("5.caseStatus=2", {**SAMPLE, "caseStatus": "2"})
    await test("6.problemLevel=2", {**SAMPLE, "problemLevel__c": "2"})
    await test("7.problemType3=89", {**SAMPLE, "problemType3__c": "89"})
    await test("8.isHandled=2", {**SAMPLE, "isHandled__c": "2"})
    await test("9.needOnSite=2", {**SAMPLE, "needOnSite__c": "2"})
    await test("10.isOffline=2", {**SAMPLE, "isOfflineApply__c": "2"})
    await test("11.isOverdue=2", {**SAMPLE, "isOverdueService__c": "2"})
    # 全量替换（仅修 problemResponsible）
    await test("12.全量(修problemResp)", {
        **SAMPLE,
        "ownerId": "101634", "name": "售后单",
        "caseSource": "6", "feedbackChannel__c": "6", "workOrderStatus__c": "3",
        "caseDescription": "测试描述test", "caseStatus": "2", "problemLevel__c": "2",
        "problemType3__c": "89",
        "problemResponsible__c": "101633",  # 用有效值
        "problemDept__c": "576825",
        "feedbackUserName__c": "向逸辉",
        "needCallBack__c": "1", "isHandled__c": "2", "needOnSite__c": "2",
        "remark__c": "1", "isOfflineApply__c": "2", "isOverdueService__c": "2",
        "caseAccountId": "CZ1000001",
        "projectName__c": "XSJH20260528003",
        "projectProvince__c": "北京市",
        "custLevel1__c": "1", "bigCustShortName__c": "测试",
        "serviceCycleStart__c": "1784797500", "serviceCycleEnd__c": "1784797500",
        "planFeedbackTime__c": "1784797500", "requireSolveTime__c": "1784797500",
        "feedbackUserContact__c": "13800138000",
    })

asyncio.run(main())
