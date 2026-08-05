"""验证完整同步流程：同一 sessionId 提交 → 重置 → 再次提交，确认销售易接口被正确调用。

模拟用户场景：
1. 获取工单，持有同一 sessionId
2. 提交确认（应调用销售易）
3. 重置工单回 pending_review
4. 用同一 sessionId 再次提交（不应被幂等误判，应再次调用销售易）
"""
import asyncio
import json
import httpx
import uuid

BASE = 'http://localhost:8093'
WID = 'wo-483e6ca0-a6f1-4d1a-9444-ff6e036760ba'
SESSION_ID = 'verify-session-001'  # 模拟前端复用同一 sessionId

async def get_version(http, wid):
    r = await http.get(f'{BASE}/api/workorders/{wid}')
    return r.json()['version']

async def submit(http, wid, version, session_id, label):
    """提交确认，返回 response。"""
    r = await http.post(f'{BASE}/api/workorders/{wid}/confirm', json={
        'session_id': session_id,
        'version': version,
        'changes': [{
            'op': 'replace',
            'path': '/name',
            'field_label': '工单主题',
            'new_value': f'{label}-{uuid.uuid4().hex[:6]}',
        }],
        'reject_reason': None,
        'review_notes': f'{label}',
        'idempotency_key': f'{label}-{uuid.uuid4().hex[:8]}',
    })
    return r

async def main():
    async with httpx.AsyncClient(timeout=30.0) as http:
        # 1. 获取锁
        r = await http.post(f'{BASE}/api/workorders/{WID}/lock', json={'user_id': 'verify-user'})
        print(f'1. 获取锁: {r.status_code} {r.json()}')

        # 2. 第一次提交（同一 sessionId）
        version = await get_version(http, WID)
        r = await submit(http, WID, version, SESSION_ID, '第一次提交')
        print(f'2. 第一次提交: {r.status_code} {r.json()}')
        if r.status_code != 200:
            print('   提交失败，终止'); return

        # 3. 等待销售易同步完成
        print('3. 等待同步...')
        await asyncio.sleep(10)
        r = await http.get(f'{BASE}/api/workorders/{WID}')
        d = r.json()
        print(f'   同步状态: {d["sync_status"]} external_id={d.get("sync_external_id")}')
        assert d['sync_status'] == 'synced', '第一次同步失败！'
        print('   ✅ 第一次同步成功')

        # 4. 重置工单回 pending_review（模拟数据库重置）
        from app.core.database import async_session
        from sqlalchemy import text
        async with async_session() as db:
            await db.execute(text('''
                UPDATE workorder_review SET review_status='pending_review', version=version+1,
                reviewed_at=NULL, reviewed_by=NULL, review_duration_seconds=NULL,
                review_started_at=NULL, review_notes=NULL, field_overrides='{}'::jsonb,
                sync_status='pending', sync_attempts=0, sync_last_error=NULL,
                sync_external_id=NULL, sync_idempotency_key=NULL,
                reject_count=0, last_reject_reason=NULL, last_rejected_by=NULL, last_rejected_at=NULL
                WHERE id = :wid
            '''), {'wid': WID})
            await db.commit()
        print('4. 工单已重置回 pending_review')

        # 5. 用同一 sessionId 再次提交（应正常同步，不应被幂等误判）
        r = await http.post(f'{BASE}/api/workorders/{WID}/lock', json={'user_id': 'verify-user'})
        print(f'5. 重新获取锁: {r.status_code}')

        version = await get_version(http, WID)
        r = await submit(http, WID, version, SESSION_ID, '重置后再提交')
        print(f'6. 第二次提交（同 sessionId）: {r.status_code} {r.json()}')
        if r.status_code != 200:
            print('   ❌ 提交失败，可能是幂等误判'); return

        # 7. 等待同步
        print('7. 等待同步...')
        await asyncio.sleep(10)
        r = await http.get(f'{BASE}/api/workorders/{WID}')
        d = r.json()
        print(f'   同步状态: {d["sync_status"]} external_id={d.get("sync_external_id")}')
        if d['sync_status'] == 'synced':
            print('   ✅ 第二次同步成功（幂等修复生效！）')
        else:
            print(f'   ❌ 第二次同步失败: {d["sync_status"]} error={d.get("sync_last_error")}')

asyncio.run(main())
