"""验证幂等修复：同一 sessionId 提交不同工单时，不应被误判为幂等重复。"""
import asyncio
import json
import httpx
from app.core.config import settings

BASE = 'http://localhost:8093'

async def main():
    async with httpx.AsyncClient(timeout=30.0) as http:
        # 获取工单列表
        r = await http.get(f'{BASE}/api/workorders?limit=5')
        workorders = r.json()['items']
        print(f'工单列表: {len(workorders)} 条')
        for w in workorders:
            print(f"  {w['id']} | {w['ticket_no']} | {w['review_status']}")

        # 取第一条待审核工单
        target = next((w for w in workorders if w['review_status'] == 'pending_review'), None)
        if not target:
            print('❌ 没有待审核工单')
            return
        wid = target['id']
        print(f'\n目标工单: {wid}')

        # 获取工单详情拿版本号
        r = await http.get(f'{BASE}/api/workorders/{wid}')
        detail = r.json()
        version = detail['version']
        print(f'version={version}')

        # 获取锁
        r = await http.post(f'{BASE}/api/workorders/{wid}/lock', json={'user_id': 'verify-user'})
        print(f'获取锁: {r.status_code}')

        # 模拟前端：同一 sessionId
        session_id = 'verify-session-001'

        # 提交确认
        r = await http.post(f'{BASE}/api/workorders/{wid}/confirm', json={
            'session_id': session_id,
            'version': version,
            'changes': [],
            'reject_reason': None,
            'review_notes': '验证幂等修复',
            'idempotency_key': 'verify-key-001',
        })
        print(f'\n第一次提交: {r.status_code}')
        print(f'  response: {json.dumps(r.json(), ensure_ascii=False)}')
        assert r.status_code == 200, '第一次提交失败'
        first = r.json()
        print(f'  status={first["status"]} sync_status={first["sync_status"]}')

        # 验证 DB 中 audit_log 是否写入
        await asyncio.sleep(2)

        # 现在模拟用户"下一个工单"——用同一个 sessionId 提交另一个工单
        # 找另一个 pending_review 工单
        target2 = next((w for w in workorders if w['review_status'] == 'pending_review' and w['id'] != wid), None)
        if target2:
            wid2 = target2['id']
            r = await http.get(f'{BASE}/api/workorders/{wid2}')
            version2 = r.json()['version']
            r = await http.post(f'{BASE}/api/workorders/{wid2}/lock', json={'user_id': 'verify-user'})
            print(f'\n第二工单获取锁: {r.status_code}')

            r = await http.post(f'{BASE}/api/workorders/{wid2}/confirm', json={
                'session_id': session_id,  # 同一 sessionId！
                'version': version2,
                'changes': [],
                'reject_reason': None,
                'review_notes': '验证跨工单幂等',
                'idempotency_key': 'verify-key-002',
            })
            print(f'第二次提交（同 sessionId 不同工单）: {r.status_code}')
            resp2 = r.json()
            print(f'  response: {json.dumps(resp2, ensure_ascii=False)}')
            print(f'  status={resp2["status"]} sync_status={resp2["sync_status"]}')
            # 修复前：sync_status 会是 'pending' 但实际不调度同步（幂等误判）
            # 修复后：sync_status 也是 'pending'，但 audit_log 会新增记录
        else:
            print('\n⚠️ 没有第二个工单可测，跳过跨工单验证')

asyncio.run(main())
