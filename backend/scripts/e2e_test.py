"""E2E 全流程测试：获取锁 → 确认提交（带字段修改）→ 等待销售易同步"""
import asyncio
import json
import httpx
from app.core.config import settings

WID = 'wo-483e6ca0-a6f1-4d1a-9444-ff6e036760ba'
BASE = 'http://localhost:8093'

async def main():
    async with httpx.AsyncClient(timeout=30.0) as http:
        # 1. 获取工单当前版本
        r = await http.get(f'{BASE}/api/workorders/{WID}')
        data = r.json()
        version = data['version']
        status = data['review_status']
        print(f'1. 当前状态: review_status={status} version={version}')

        if status != 'pending_review':
            print('   工单不是待审核状态，请先复位')
            return

        # 2. 获取编辑锁
        r = await http.post(f'{BASE}/api/workorders/{WID}/lock',
            json={'user_id': 'e2e-user'})
        lock = r.json()
        print(f'2. 获取锁: {r.status_code} locked={lock.get("locked")}')

        if r.status_code != 200:
            print('   获取锁失败')
            return

        # 3. 确认提交（带字段修改 — 触发 JSON 序列化）
        import time
        ts = str(int(time.time()))
        body = {
            'session_id': f'sess-e2e-{ts}',
            'version': version,
            'changes': [
                {
                    'op': 'replace',
                    'path': '/name',
                    'field_label': '工单主题',
                    'new_value': '售后单-E2E已审核',
                }
            ],
            'reject_reason': None,
            'review_notes': 'E2E测试-审核通过',
            'idempotency_key': f'e2e-{ts}',
        }
        r = await http.post(f'{BASE}/api/workorders/{WID}/confirm', json=body)
        result = r.json()
        print(f'3. 确认提交: {r.status_code}')
        print(f'   {json.dumps(result, ensure_ascii=False)}')

        if r.status_code != 200:
            print(f'   ❌ 提交失败: {result}')
            return

        # 4. 等待销售易异步同步完成
        print('4. 等待销售易同步...')
        await asyncio.sleep(12)

        # 5. 验证最终状态
        r = await http.get(f'{BASE}/api/workorders/{WID}')
        final = r.json()
        print(f'5. 最终状态:')
        print(f'   review_status: {final["review_status"]}')
        print(f'   sync_status: {final["sync_status"]}')
        print(f'   sync_external_id: {final.get("sync_external_id")}')
        print(f'   field_overrides: {json.dumps(final.get("field_overrides"), ensure_ascii=False)}')

        if final['sync_status'] == 'synced':
            print('\n✅ E2E 全流程通过！')
        else:
            print(f'\n⚠️ 同步状态异常: {final["sync_status"]}')

asyncio.run(main())
