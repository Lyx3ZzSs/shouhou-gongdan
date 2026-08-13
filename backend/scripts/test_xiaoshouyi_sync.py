"""
销售易服务工单接口联调测试脚本

测试流程:
  1. OAuth2 Token 获取
  2. insertServiceCase 接口调用（真实 API）
  3. 现有数据兼容性检查
  4. 完整同步管线分析

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/test_xiaoshouyi_sync.py
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any

import httpx


# ==============================================================================
# Config — 从 .env 读取销售易配置
# ==============================================================================

class TestConfig:
    TOKEN_URL = "https://login.xiaoshouyi.com/auc/oauth2/token"
    BASE_URL = "http://221.122.90.202:6661"
    CLIENT_ID = ""
    CLIENT_SECRET = ""
    REDIRECT_URI = "https://api-tencent.xiaoshouyi.com"
    USERNAME = ""
    PASSWORD = ""

    @classmethod
    def from_env(cls):
        """从 .env 文件读取配置。"""
        import os
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        mapping = {
                            "XIAOSHOUYI_TOKEN_URL": "TOKEN_URL",
                            "XIAOSHOUYI_BASE_URL": "BASE_URL",
                            "XIAOSHOUYI_CLIENT_ID": "CLIENT_ID",
                            "XIAOSHOUYI_CLIENT_SECRET": "CLIENT_SECRET",
                            "XIAOSHOUYI_REDIRECT_URI": "REDIRECT_URI",
                            "XIAOSHOUYI_USERNAME": "USERNAME",
                            "XIAOSHOUYI_PASSWORD": "PASSWORD",
                        }
                        if k in mapping:
                            setattr(cls, mapping[k], v)
        return cls


# ==============================================================================
# Step 1: Token 获取测试
# ==============================================================================

async def test_auth(config: TestConfig) -> dict[str, str]:
    """测试 OAuth2 password grant 认证流程。"""
    print("=" * 72)
    print("Step 1: OAuth2 Token 获取测试")
    print("=" * 72)
    print(f"  Token URL: {config.TOKEN_URL}")

    if not config.CLIENT_ID:
        print("  ❌ XIAOSHOUYI_CLIENT_ID 未配置，跳过")
        return {}

    payload = {
        "grant_type": "password",
        "client_id": config.CLIENT_ID,
        "client_secret": config.CLIENT_SECRET,
        "redirect_uri": config.REDIRECT_URI,
        "username": config.USERNAME,
        "password": config.PASSWORD,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(
                config.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            print(f"  HTTP Status: {resp.status_code}")
            data = resp.json()

            if resp.status_code == 200 and "access_token" in data:
                token_preview = data["access_token"][:40] + "..."
                print(f"  ✅ Token 获取成功: {token_preview}")
                print(f"     expires_in: {data.get('expires_in')}s")
                print(f"     token_type: {data.get('token_type')}")
                print(f"     instance_uri: {data.get('instance_uri')}")
                return {
                    "access_token": data["access_token"],
                    "token_type": data.get("token_type", "Bearer"),
                    "expires_in": str(data.get("expires_in", 0)),
                }
            else:
                print(f"  ❌ Token 获取失败: {json.dumps(data, ensure_ascii=False)}")
                return {}
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        return {}


# ==============================================================================
# Step 2: insertServiceCase 接口测试
# ==============================================================================

# 必填字段 = API 文档必填 ∪ field_config.yaml required_keys（与 xiaoshouyi.py 的 _REQUIRED_FIELDS 保持一致）
REQUIRED_FIELDS = [
    "ownerId", "dimDepart", "entityType", "name",
    "caseAccountId", "projectName__c",
    "problemResponsible__c", "problemDept__c",
    # 以下 5 个来自 field_config.yaml required: true
    "caseStatus", "caseSource", "workOrderStatus__c",
    "caseDescription", "feedbackChannel__c",
]

# API 文档中的示例请求体（来自 docs/销售易服务工单接口文档.md）
SAMPLE_REQUEST = {
    "ownerId": "101633",
    "dimDepart": "sprixin",
    "entityType": "11010045500001",
    "name": "测试工单-联调验证",
    "caseSource": "1",
    "feedbackChannel__c": "1",
    "workOrderStatus__c": "1",
    "caseDescription": "这是一条联调测试工单，用于验证销售易服务工单新增接口。",
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
    "remark__c": "联调测试备注",
    "planFeedbackTime__c": "1784797500",
    "requireSolveTime__c": "1784797500",
    "defectFlag__c": "1",
}


async def test_insert_service_case(
    config: TestConfig, token_info: dict[str, str]
) -> bool:
    """测试 insertServiceCase 接口。"""
    print("\n" + "=" * 72)
    print("Step 2: insertServiceCase 接口测试")
    print("=" * 72)

    if not token_info:
        print("  ⏭ 跳过（无有效 token）")
        return False

    url = f"{config.BASE_URL.rstrip('/')}/openapi/insertServiceCase"
    token = f"{token_info['token_type']} {token_info['access_token']}"
    print(f"  URL: {url}")

    # 发送 API 文档中的示例请求
    body = dict(SAMPLE_REQUEST)
    body["name"] = f"测试工单-联调验证-{datetime.now().strftime('%m%d%H%M%S')}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": token,
                },
            )
            print(f"  HTTP Status: {resp.status_code}")
            raw = resp.json() if resp.status_code < 500 else {}
            print(f"  Response: {json.dumps(raw, ensure_ascii=False, indent=2)}")

            code = raw.get("code", "")
            # 实际 API 返回整数 200，文档中为字符串 "200" — 兼容两种
            if resp.status_code == 200 and str(code) == "200":
                ext_id = raw.get("data", {}).get("dataId") or raw.get("data", {}).get("id")
                print(f"  ✅ 工单创建成功: external_id={ext_id}")
                return True
            else:
                msg = raw.get("message") or raw.get("msg", "")
                print(f"  ❌ 工单创建失败: code={code} msg={msg}")
                return False
    except Exception as e:
        print(f"  ❌ 请求异常: {e}")
        return False


# ==============================================================================
# Step 3: 最小请求体测试（仅必填字段）
# ==============================================================================

async def test_minimal_request(
    config: TestConfig, token_info: dict[str, str]
) -> bool:
    """仅发送必填字段，测试 API 的最小接受度。"""
    print("\n" + "=" * 72)
    print("Step 3: 最小请求体测试（仅必填字段）")
    print("=" * 72)

    if not token_info:
        print("  ⏭ 跳过（无有效 token）")
        return False

    url = f"{config.BASE_URL.rstrip('/')}/openapi/insertServiceCase"
    token = f"{token_info['token_type']} {token_info['access_token']}"

    minimal = {
        "ownerId": "101633",
        "dimDepart": "sprixin",
        "entityType": "11010045500001",
        "name": f"最小字段测试-{datetime.now().strftime('%m%d%H%M%S')}",
        "caseAccountId": "SPCZ202408210132",
        "projectName__c": "XSJH20260723012",
        "problemResponsible__c": "101633",
        "problemDept__c": "sprixin",
        "caseStatus": "1",
        "caseSource": "1",
        "workOrderStatus__c": "1",
        "caseDescription": "最小字段测试",
        "feedbackChannel__c": "1",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                url,
                json=minimal,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": token,
                },
            )
            print(f"  HTTP Status: {resp.status_code}")
            raw = resp.json() if resp.status_code < 500 else {}
            print(f"  Response: {json.dumps(raw, ensure_ascii=False, indent=2)}")

            code = raw.get("code", "")
            if resp.status_code == 200 and str(code) == "200":
                ext_id = raw.get("data", {}).get("dataId") or raw.get("data", {}).get("id")
                print(f"  ✅ 最小字段请求成功: external_id={ext_id}")
                return True
            else:
                msg = raw.get("message") or raw.get("msg", "")
                print(f"  ❌ 失败: code={code} msg={msg}")
                return False
    except Exception as e:
        print(f"  ❌ 请求异常: {e}")
        return False


# ==============================================================================
# Step 4: 代码与文档一致性分析
# ==============================================================================

async def analyze_code_doc_alignment(config: TestConfig):
    """对比代码实现与 API 文档的差异。"""
    print("\n" + "=" * 72)
    print("Step 4: 代码与文档一致性分析")
    print("=" * 72)

    # 读取现有 DB 数据，检查格式兼容性
    try:
        from app.core.database import async_session
        from app.models.ticket import TicketView
        from sqlalchemy import select
    except ImportError as e:
        print(f"  ⚠ 无法导入 app 模块: {e}")
        print("  跳过 DB 数据分析（可能是 PYTHONPATH 问题）")
        return

    issues = []

    async with async_session() as db:
        r = await db.execute(select(TicketView))
        tickets = r.scalars().all()

        for t in tickets[:5]:  # 采样前 5 条
            d = t.to_dict()
            tn = d["ticket_no"]

            # 检查时间戳字段格式
            for ts_field in [
                "serviceCycleStart__c", "serviceCycleEnd__c",
                "planFeedbackTime__c", "requireSolveTime__c",
            ]:
                val = d.get(ts_field)
                if val:
                    # 必须是 Unix 时间戳（全数字字符串）
                    if not str(val).isdigit():
                        issues.append(
                            f"  ❌ {tn}.{ts_field}={val!r} — API 要求 Unix 时间戳"
                            f"（如 '1784797500'），实际是日期字符串"
                        )

            # 检查必填字段非空
            for rf in REQUIRED_FIELDS:
                val = d.get(rf)
                if val is None or str(val).strip() == "":
                    issues.append(
                        f"  ❌ {tn}.{rf} 为空 — 此字段是 API 必填字段"
                    )

    if issues:
        print("\n  发现以下问题:\n")
        for issue in issues:
            print(issue)
    else:
        print("  ✅ 未发现问题")

    # 检查代码中的字段映射
    from app.clients.xiaoshouyi import DB_TO_API_FIELD_MAP

    # 找出 DB_TO_API_FIELD_MAP 中不在 API 文档里的字段
    doc_fields = set(SAMPLE_REQUEST.keys())
    code_fields = set(DB_TO_API_FIELD_MAP.keys())
    extra_in_code = code_fields - doc_fields
    missing_in_code = doc_fields - code_fields

    if extra_in_code:
        print(f"\n  ⚠ 代码中有但文档中无的字段: {extra_in_code}")
    if missing_in_code:
        print(f"\n  ❌ 文档中有但代码中无的字段: {missing_in_code}")
    if not extra_in_code and not missing_in_code:
        print("\n  ✅ 字段映射与文档完全一致")

    # 检查 to_api_body() 行为 — 必填字段过滤问题
    print("\n  --- to_api_body() 行为分析 ---")
    print("  当前逻辑: 空字符串/None 的字段会被排除")
    print("  风险: 如果必填字段（如 ownerId, dimDepart）为 None，")
    print("        会被静默排除，导致 API 拒绝请求")
    print("  建议: 必填字段始终发送（即使为空），可选字段可排除")


# ==============================================================================
# Step 5: 完整同步管线测试（含本地数据）
# ==============================================================================

async def test_full_pipeline(config: TestConfig, token_info: dict[str, str]):
    """使用真实 DB 数据 + 真实 API 测试完整同步流程。"""
    print("\n" + "=" * 72)
    print("Step 5: 完整同步管线测试（本地数据 → 销售易 API）")
    print("=" * 72)

    if not token_info:
        print("  ⏭ 跳过（无有效 token）")
        return

    try:
        from app.core.database import async_session
        from app.clients.xiaoshouyi import map_db_to_xiaoshouyi
        from sqlalchemy import text
    except ImportError as e:
        print(f"  ⚠ 无法导入 app 模块: {e}")
        return

    url = f"{config.BASE_URL.rstrip('/')}/openapi/insertServiceCase"
    token = f"{token_info['token_type']} {token_info['access_token']}"

    async with async_session() as db:
        # 使用 raw SQL 避免 ORM relationship 导入问题
        r = await db.execute(
            text("SELECT * FROM workorder_review WHERE review_status = 'pending_review' LIMIT 1")
        )
        wo_row = r.mappings().first()
        if wo_row is None:
            print("  ⚠ 无可用工单")
            return

        # 获取 ticket_view 数据
        r = await db.execute(
            text("SELECT * FROM ticket_view WHERE ticket_no = :tn"),
            {"tn": wo_row["ticket_no"]},
        )
        ticket_row = r.mappings().first()
        if ticket_row is None:
            print(f"  ❌ ticket_no={wo_row['ticket_no']} 在 ticket_view 中不存在")
            return

        # merge: ticket_view 原始值 + field_overrides 覆盖
        ticket_dict = dict(ticket_row)
        overrides = wo_row.get("field_overrides") or {}
        merged = {**ticket_dict, **overrides}
        print(f"  ticket_no: {wo_row['ticket_no']}")
        print(f"  merge keys: {len(merged)}")
        print(f"  overrides: {json.dumps(overrides, ensure_ascii=False)}")

        # 构建请求
        req = map_db_to_xiaoshouyi(merged)
        body = req.to_api_body()
        print(f"\n  --- 实际发送的 API Body ---")
        print(f"  {json.dumps(body, ensure_ascii=False, indent=4)[:2000]}")

        # 检查必填字段
        missing_required = [f for f in REQUIRED_FIELDS if f not in body]
        if missing_required:
            print(f"\n  ⚠ 缺少必填字段: {missing_required}")
            print("  这些字段在 DB 中为空，被 to_api_body() 过滤掉了")

        # 检查时间戳字段
        for ts_field in [
            "serviceCycleStart__c", "serviceCycleEnd__c",
            "planFeedbackTime__c", "requireSolveTime__c",
        ]:
            val = body.get(ts_field)
            if val and not str(val).isdigit():
                print(f"  ⚠ {ts_field}={val!r} 不是时间戳格式")

        # 确认是否发送
        print(f"\n  发送到: {url}")
        print(f"  确认发送? (y/n): ", end="")
        # 自动化运行时不交互，跳过
        print("[跳过 — 自动化模式]")


# ==============================================================================
# Main
# ==============================================================================

async def main():
    print("销售易服务工单接口联调测试")
    print(f"执行时间: {datetime.now().isoformat()}")
    print()

    config = TestConfig.from_env()
    print(f"BASE_URL: {config.BASE_URL or '(未配置)'}")
    print(f"CLIENT_ID: {'***' if config.CLIENT_ID else '(未配置)'}")

    if not config.CLIENT_ID or not config.BASE_URL:
        print("\n⚠ 销售易配置不完整，仅执行离线分析（Step 4）。")
        print("  请在 .env 中配置以下变量以启用在线测试:")
        print("    XIAOSHOUYI_BASE_URL=http://221.122.90.202:6661")
        print("    XIAOSHOUYI_CLIENT_ID=<your_client_id>")
        print("    XIAOSHOUYI_CLIENT_SECRET=<your_client_secret>")
        print("    XIAOSHOUYI_USERNAME=<your_username>")
        print("    XIAOSHOUYI_PASSWORD=<your_password>")

    # Step 1: Auth
    token_info = await test_auth(config)

    # Step 2: Full request test
    await test_insert_service_case(config, token_info)

    # Step 3: Minimal request test
    await test_minimal_request(config, token_info)

    # Step 4: Code-doc alignment (offline)
    await analyze_code_doc_alignment(config)

    # Step 5: Full pipeline test
    await test_full_pipeline(config, token_info)

    print("\n" + "=" * 72)
    print("测试完成")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
