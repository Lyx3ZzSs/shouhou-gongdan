"""字段排查：逐个替换测试数据字段，定位导致销售易 NPE 的具体字段。"""
import asyncio, json, httpx

async def get_token():
    from app.core.config import settings
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
    from app.core.config import settings
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
    # SAMPLE_REQUEST 已验证成功，以此为基
    base = {
        "ownerId": "101633", "dimDepart": "sprixin", "entityType": "11010045500001",
        "name": "字段排查", "caseSource": "1", "feedbackChannel__c": "1",
        "workOrderStatus__c": "1", "caseDescription": "排查NPE",
        "caseStatus": "1", "caseAccountId": "SPCZ202408210132",
        "custLevel1__c": "1", "projectName__c": "XSJH20260723012",
        "projectProvince__c": "北京市", "bigCustShortName__c": "测试大客户",
        "serviceCycleStart__c": "1784797500", "serviceCycleEnd__c": "1784797500",
        "isOfflineApply__c": "1", "isOverdueService__c": "1",
        "problemLevel__c": "1", "problemType1__c": "1", "problemType2__c": "1",
        "problemType3__c": "1", "feedbackCount__c": "1",
        "problemResponsible__c": "101633", "problemDept__c": "sprixin",
        "feedbackUserName__c": "测试用户", "feedbackUserContact__c": "13800138000",
        "needCallBack__c": "1", "isHandled__c": "1", "needOnSite__c": "1",
        "remark__c": "测试", "planFeedbackTime__c": "1784797500",
        "requireSolveTime__c": "1784797500", "defectFlag__c": "1",
    }

    # 测试数据（用户提供的值）
    user = {
        "ownerId": "101634", "dimDepart": "sprixin",
        "name": "售后单",
        "caseSource": "6", "feedbackChannel__c": "6", "workOrderStatus__c": "3",
        "caseDescription": "客户发送了多个售后单测试",
        "caseStatus": "2", "problemLevel__c": "2",
        "problemType1__c": "1", "problemType2__c": "1", "problemType3__c": "89",
        "feedbackCount__c": "1",
        "problemResponsible__c": "100658", "problemDept__c": "576825",
        "feedbackUserName__c": "向逸辉",
        "needCallBack__c": "1", "isHandled__c": "2", "needOnSite__c": "2",
        "remark__c": "1",
        "caseAccountId": "CZ1000001",
        "projectName__c": "XSJH20260528003",
        "projectProvince__c": "北京市",
        "isOfflineApply__c": "2", "isOverdueService__c": "2",
        # 保持安全值
        "custLevel1__c": "1", "bigCustShortName__c": "测试",
        "feedbackUserContact__c": "13800138000",
        "serviceCycleStart__c": "1784797500", "serviceCycleEnd__c": "1784797500",
        "planFeedbackTime__c": "1784797500", "requireSolveTime__c": "1784797500",
    }

    # 测试1: 全部替换（已修安全值）
    await test("1.全替换(安全值)", {**base, **user})

    # 测试2: 逐个排查空值字段
    await test("2.空custLevel1", {**base, **user, "custLevel1__c": ""})
    await test("3.空bigCust", {**base, **user, "bigCustShortName__c": ""})
    await test("4.双空", {**base, **user, "custLevel1__c": "", "bigCustShortName__c": ""})

    # 测试5: 9位时间戳
    await test("5.9位时间戳", {**base, **user,
        "serviceCycleStart__c": "178497500", "serviceCycleEnd__c": "178497500"})

    # 测试6: 邮箱contact
    await test("6.邮箱contact", {**base, **user,
        "feedbackUserContact__c": "10101333333@qq.com"})

    # 测试7: caseAccountId = CZ1000001
    await test("7.CZ1000001", {**base, **user, "caseAccountId": "CZ1000001"})

    # 测试8: 所有风险因素组合
    await test("8.全风险组合", {**base, **user,
        "custLevel1__c": "", "bigCustShortName__c": "",
        "serviceCycleStart__c": "178497500", "serviceCycleEnd__c": "178497500",
        "feedbackUserContact__c": "10101333333@qq.com",
    })

asyncio.run(main())
