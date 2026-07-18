# 工单审查系统 架构 Review 报告

> Review 范围：后端 FastAPI + 前端 React 三栏工作台。日期 2026-07-18。
> 方法：业务基线提炼 → 后端/前端/开源方案 3 路并行深度 Review → 主审亲自核验 8 项最严重指控（全部属实）。

---

## 0. 系统边界（Review 前置，已与用户确认）

本系统是更大平台（spec SRS V0.2 定义 6 大 FR）的**一个子系统**，只负责"人工审核"环节：

```
[外部 AI 系统] --写--> workorder 表(共享DB) --本系统读--> 审核工作台 --人工审核-->
   通过 --API同步--> [销售易工单系统]   /   退回驳回 --> 回到 pending_review
```

- **输入**：共享 DB 的 workorder 表，由外部 AI 系统自动生成写入（本系统只读源数据，审核时改白名单字段）
- **处理**：人工审核工作台（读 DB -> 逐字段核对 -> 修改/确认/退回/驳回）
- **输出**：审核通过 -> 调销售易 API 创建工单（**系统唯一业务输出**）
- **不在范围**（spec 其他 FR，由其他系统实现）：多渠道接入 / AI 身份核验 / AI 智能处理 / 智能派单 / 跨部门协同 / AI 准确性评测

> ⚠️ 第一版 Review 误把"未实现上述 6 大 FR"当成差距，已更正。本 Review 只对照"人工审核 + 销售易对接"这一段找问题。边界澄清使**销售易同步从边缘功能升格为最高优先级核心输出**。

---

## 一、总体结论

| 维度 | 评分 | 一句话 |
|---|---|---|
| 后端生产就绪度 | **4/10** | 功能闭环，但锁原子性、同步可靠性、migration 一致性均有阻断性缺陷 |
| 前端生产就绪度 | **3/10** | UI 完成度高，但持久化/并发/冲突/竞态全是"演"的 |
| 架构分层 | 7/10 | 后端 router→service→model 基本合理，读路径 SQL 泄漏在 router |
| 组件与 UX 设计 | 8/10 | 三栏布局、快捷键、阻断/定位/回退移除等核心交互逻辑正确 |
| 可观测性 | 2/10 | spec 要求的 trace_id + 服务/模型/规则版本回传完全缺失 |

**核心判断**：本项目最大的风险不是 bug 数量，而是 **"mock 给了已就绪的假象"**——新工作台 UI 精致、交互流畅，但自动暂存不落盘、锁丢失不阻断、冲突合并不真实、队列筛选部分失效。一旦切真实 API，这些都会变成线上事故。spec 的 P0 红线（错关联客户/项目、跨客户串用等）属于 AI 生成环节，不在本系统范围。但本系统对应的红线--**审核通过后工单必须可靠进入销售易**--当前是空壳实现（见 B8），系统无法完成其唯一业务使命。

**已核验**：下文所有 🔴 严重项均由主审 Read 源码逐行确认，非子代理推测。

---

## 二、🔴 致命问题（已核验，上线阻断）

### 后端

**B1. 分布式锁 release/heartbeat 非原子（TOCTOU）— `lock_service.py:75-97`**
`release()` 与 `heartbeat()` 均为 `GET 校验 owner → DELETE/EXPIRE` 两步，中间无原子保护。在 GET 与 DELETE 之间锁若过期并被他人 acquire，`DELETE` 会**误删他人锁**，heartbeat 同理会为他人续期。"仅持有者可释放"在并发下形同虚设。
→ 修复：用 Lua 脚本原子化 `if redis.call('get',k)==v then return redis.call('del',k) end`。`acquire()` 在 SET NX 失败后 GET 之间过期的兜底（70-72 行直接 SET 不带 NX）也有同样隐患，应一并改为 CAS 循环或 Lua。

**B2. migration 缺 `sync_status` 列 — `001_add_review_tables.py` vs `workorder.py:25`**
Model 定义了 `sync_status`，`review_service` 的 UPDATE 写了 `sync_status='pending'`，但 migration 只 add 了 version/reviewed_at 等 7 列，**没有 sync_status**。生产 workorder 表（132 列预存）若没有此列，`_execute_confirm` 的 UPDATE 会直接报错。`test_review_integration.py:120` 手动 CREATE TABLE 时补了这列，掩盖了问题。
→ 修复：migration 补 `sa.Column('sync_status', sa.String(16), nullable=False, server_default='pending')`。

**B3. WorkOrder.id 类型不一致 — `workorder.py:15`**
Model 是 `Integer`，但 schema(`WorkOrderResponse.id: str`)、router(`workorder_id: str`)、`audit_log.workorder_id(String(64))`、测试数据(`"WO-E2E-001"`)全是字符串。SQLite 隐式转换掩盖，MySQL 8 会异常。
→ 修复：统一为 `String(64)` 业务编号做主键，或全栈改 int。

**B4. JWT_SECRET 公开默认值无启动校验 — `config.py:5`**
`JWT_SECRET: str = "dev-secret-change-in-production"`，无 `@field_validator`。生产漏配环境变量则密钥是公开常量，任何人可签发合法 token 冒充任意 agent。
→ 修复：生产环境校验 SECRET 非默认且长度≥32。

**B5. 后台同步任务时序错误 + 无持久化 — `review_service.py:116,208-246`**
`_schedule_sync` 在 `async with self.db.begin()` 事务**未提交**时就 `asyncio.create_task(_sync())`。sync 任务用新 session 读 workorder，可能读到 commit 前旧状态；task 引用未保存可能被 GC；进程重启则任务丢失，`sync_status` 永远停在 pending。
→ 修复：用 Celery/arq/RQ 持久化队列，或至少 commit 后调度 + after_commit hook。

**B6. xiaoshouyi 同步失败被静默吞掉 — `review_service.py:231-232`**
`except NotImplementedError: logger.info(跳过同步)`，但 `sync_status` 既不置 failed 也不重试，客户端看到 `sync_status="pending"` 以为还在同步。**当前所有 confirm 都进入"永久 pending"**（客户端未实现）。
→ 修复：置 `sync_status='failed'` 或返回明确未实现错误，配重试/死信。

**B7. 无 workorder 级权限校验（越权）— `review.py` 全部端点**
`get_current_user` 只校验角色是 `customer_service_agent`，任何 agent 可操作任意 workorder（含他人锁定的）。confirm 的 finally 里 release 锁，但**入口处没有 acquire 校验**，锁形同虚设。
→ 修复：review/confirm 前校验当前用户即锁持有者或 acquire 成功。

**B8. 销售易同步是空壳 -- 系统唯一业务输出无法完成（最高优先级）- `xiaoshouyi.py:60` + `review_service.py:231` + `CreateWorkOrderRequest:13-16`**
系统的核心使命是"审核通过 -> 同步销售易"，但实现是三层空壳：
1. `XiaoShouYiClient.create_work_order` 直接 `raise NotImplementedError`（line 60-62），HTTP 调用全注释掉。
2. `_schedule_sync` 捕获 `NotImplementedError` 后仅 `logger.info("销售易客户端未实现，跳过同步")`（review_service.py:231-232），**既不置 sync_status='failed' 也不重试**，sync_status 永远停在 'pending'。审核员看到"通过"成功，但工单**永远不会进入销售易**，下游客户服务断链。
3. `CreateWorkOrderRequest` 只有 `idempotency_key`，**没有工单字段映射**（line 16 TODO: 补充 28 个字段）。即使补上 HTTP 调用，也没把审核后的工单内容（站点/项目/分类/描述等）传给销售易。
4. 叠加 B5：`asyncio.create_task` 在事务未提交时启动、无持久化、进程重启丢失。
-> 这不是"待实现功能"，而是"系统当前无法完成核心使命"。修复需：实现 HTTP 调用 + 字段映射 + 持久化任务队列（Celery/arq）+ sync_status 正确流转（pending->synced/failed）+ 失败重试与对账 + 销售易返回 external_id 回写。

**B9. 共享数据库集成契约缺失 -- 与外部 AI 系统的并发与所有权未约定**
本系统读改写 workorder 表，外部 AI 系统也写同一张表（132+ 列，本系统只建模 35 列）。这是高耦合的共享 DB 集成，但关键契约未约定/未实现：
1. **version 所有权**：本系统 confirm 时 `version = version + 1` 并 `WHERE version = :version` 做乐观锁。但外部系统更新工单时**是否 bump version**？若外部系统直接 UPDATE 不检查 version，本系统乐观锁被绕过，审核中途外部改了字段，冲突检测不到。
2. **status 流转所有权**：confirm 要求 `WHERE status = 'pending_review'`。**谁负责把工单置为 'pending_review'**？若外部系统写入时不设此状态，confirm 永远 rowcount=0 -> 409。本系统无任何端点设置 pending_review，依赖外部系统契约，但契约未文档化。
3. **97 列不可见**：本系统 WorkOrderResponse 只返回 35 列，其余 97 列审核员看不到。若其中有影响审核判断的字段（如历史工单关联、设备档案），**审核员在信息不全时做决策**，业务正确性风险。
4. **读新鲜度**：审核员打开工单后，外部系统可能更新同一行。本系统无机制感知（无推送/轮询/etag）。originalValue 过期但审核员仍基于旧值判断。乐观锁只在提交时校验，若外部不 bump version 则检测不到。
5. **bad_case 的 ai_value 来源假设脆弱**：`bad_case_service` 把变更前列值当 AI 原始值。前提是"读取时列值=AI 生成原始值且未被改过"。在共享库 + 外部可能二次更新下，此假设不成立。建议外部系统写入时快照 ai_prediction，而非依赖当前列值。
-> 修复需与外部系统团队对齐契约：version/status 流转责任、可见列范围、变更通知机制（或本系统定时轮询+前端 ETag 刷新）、ai_prediction 快照。这是架构级协调，非单点代码修复。

### 前端

**F1. 自动暂存从不真正落盘 — `useAutoSave.ts:1-36`**
整个 hook 只在 `'saving'→'saved'` 之间切 label（1s 定时器 + 30s interval），**没有任何 fetch/API 调用**。`stash()` 也只改本地状态。刷新/关浏览器所有修改丢失。spec 要求的 4 种触发（停输入/失焦/切单/定时）只有两个被模拟且只改 label，blur 触发完全缺失。
→ 修复：store 加 `changeTick` 计数器驱动 debounce；引入真实暂存 API；FieldEditInline 加 onBlur 保存。

**F2. 锁丢失后不阻断编辑 — `useReviewLock.ts:45-60`**
心跳返回 `'lost'` 仅设 banner `"锁已丢失，请刷新页面"` 并停心跳，**不释放、不禁用编辑、不弹窗强阻塞**。用户继续修改并提交必失败但已被误导。旧页 `useReviewLock.ts` 至少有 `message.error` 持续提示，新工作台反而退化。
→ 修复：锁丢失进 `lockLost` 终态，禁用 setFieldValue/submit，弹窗强制刷新；他人持锁转只读。

**F3. resolveConflict('merge') 是假合并 — `useReviewStore.ts:626-631`**
仅本地把 version 改成 `theirVersion+1`，**不 re-fetch、不比对双方重叠字段、不真正合并**。若对方改了同字段，本地 `originalValue` 已过期，下次 submit 的 `old_value` 脏。且 `idempotency_key: sessionId` 跨重试不变，后端幂等缓存会返回首次失败结果。
→ 修复：merge 必须 `fetchWorkOrder` 拿最新 version+内容再重放 effectiveChanges；`idempotency_key` 每次 submit 用新 UUID。

**F4. loadTicketById 无竞态保护 + StrictMode 双调用 — `useReviewStore.ts:307-340` + `main.tsx:7`**
快速 J/K 或双击队列项时多个 `loadTicketById` 并发，`set` 按响应到达顺序写入，**最后到达覆盖选中项**，可能显示非用户期望工单。`<React.StrictMode>` 下 `init()` 双调用加剧竞态。
→ 修复：store 维护 `currentLoadSeq`，响应回来比对丢弃过期；或 AbortController。

**F5. 移动端遮罩永不显示 — `ReviewWorkbench.tsx:83,105`**
`className="hidden max-lg:fixed max-lg:inset-0..."`：`hidden`=`display:none`，`max-lg:fixed` 只改定位**不覆盖 display**。移动端展开队列/侧栏无遮罩，用户无法点空白关闭、下层可点。
→ 修复：改 `lg:hidden max-lg:fixed`。

**F6. source 筛选恒为空 — `useReviewStore.ts:107`**
`if (f.source !== 'all' && item.type !== f.source) return false;` 比较 `item.type`（"设备故障"）而非来源字段，与 SOURCE_OPTIONS（"监控告警自动生成/用户报修"）永不相等。注释自承"简化"，但实际是失效筛选。
→ 修复：QueueItem 增加 `source` 字段，mock/converter 填充。

**F7. mock 数据模型与真实 API 完全不重叠 — `mock/mockData.ts` vs `converters.ts:56-119`**
mock 用 `contactName/contactPhone/faultDesc/categoryL1/region/priority`；converter 用 `customer_name/responsible_person/problem_description/problem_category_l1/project_province/order_level`。**两套字段 id 完全不同**，mock 阶段验证的异常规则/分组/关键字段切真实数据后全部失效。`workOrderSummaryToQueueItem` 把 type/riskLevel/sla/anomalyCount/urgency 全硬编码，真实队列所有项显示相同风险/SLA，队列筛选形同虚设。
→ 修复：mock 走 `workOrderDataToReviewTicket` 同一条转换路径（用 GeneratedWorkOrderResponse 形态 mock），或明确 mock 仅布局演示。

---

## 三、后端架构评估

### 分层（7/10）
router→service→model 基本清晰，依赖方向正确无循环。但：
- 读路径 SQL 泄漏在 router（`review.py:18-40,43-100,140-171` 直接 ORM 查询 + 手工拼装 35+ 字段，而 schema 已配 `from_attributes=True`，应直接 `model_validate`）
- `_schedule_sync` 在 service 内直连 engine 创建 session，绕过 db 抽象，是分层漏洞
- 建议补 `WorkOrderQueryService` 承接读路径

### 并发与锁（2/10）— 见 B1/B7，最大风险
除 TOCTOU 外：
- `owner_name` 含 `:` 会解析错乱（`lock_service.py:45,55,81`，`split(":",maxsplit=2)` 仅保护 timestamp 段，operator_id 含 `:` 如 LDAP DN 会错判）→ 改 JSON
- `_execute_confirm` 的 finally release 锁，但入口无 acquire 校验（B7）

### 事务与一致性（5/10）
- 嵌套事务语义不清（`review_service.py:38,185`）：`get_db()` yield 的 session 在 SA 2.0 async 默认 autocommit=False，再 `async with self.db.begin()` 启动 SAVEPOINT，HTTPException 后依赖 get_db 退出隐式回滚，语义脆弱
- 字段更新 N+1 写入（`review_service.py:85-91` 循环单字段 UPDATE）→ 合并为一次 `update().where().values({...})`
- 审计日志与业务操作同事务（好），但 `_build_existing_response` 幂等返回 status 靠猜（`review_service.py:248-256`，按本次 reject_reason 推断历史状态而非查审计日志）

### 安全（3/10）
- B4 JWT 默认密钥
- B7 无 workorder 级越权校验
- `dependencies.py:44` 把 JWT 异常 detail 回传客户端，可能泄漏
- `decode_jwt` 未显式 `options={"require":["exp"]}`
- CORS origin 硬编码 `localhost:5173`（`main.py:19`）

### 数据模型（5/10）
- B2/B3 migration 与 model 不一致
- `version/status/sync_status` 高频查询/更新条件但无索引
- `audit_log.workorder_id` 是 String 但无 FK 到 workorder.id（类型也不匹配）
- `bad_case` 索引名 model `idx_workorder` vs migration `idx_badcase_workorder`，不一致
- `bad_case_service.py:24` `str(c.old_value)` 若 old_value 是 dict/list 会丢结构 → JSON 序列化

### 外部集成（3/10）
`xiaoshouyi.py` 刚起步，B6 同步失败静默；`get_xiaoshouyi_client()` 每次新建非单例；无超时/重试/降级；CRM/CTI 鉴权与字段映射空白（spec 未指明销售易 API 版本/呼叫系统厂商）。

### API 设计（5/10）
- `review` 与 `confirm` 端点功能重叠（confirm 是 review 超集 + idempotency_key），review 应废弃
- 无分页（`list_workorders` limit 50 写死）
- 无 API 版本前缀（`/v1/`）
- `release_lock` 返回 `{"status":"released"}` 但 `response_model=LockStatus` 字段不匹配，FastAPI 过滤成 `{}`
- spec 强调 dry-run/幂等，但 `idempotency_key` 默认 `""` 空串去重失效

### 测试（4/10）
- 正常流程覆盖
- **缺失**：并发冲突测试（两请求同时 review 同 workorder 验 409）、审计原子性测试（audit 写失败 workorder 是否回滚）、锁 TOCTOU 测试
- `test_lock_api.py` 依赖真实 Redis，CI 不可复现
- `test_review_api.py:18` 用 `MagicMock()` 替代 AsyncSession，隐藏异步类型问题
- `test_auth.py:40-46` 测 mock 行为而非真实 decode_jwt

### 可观测性（2/10）
spec 明确要求回传 trace_id + 服务/模型/Prompt/规则版本，但 audit_log model 和 schema 都无这些字段。无结构化日志、无监控点。

---

## 四、前端架构评估

### 状态管理（5/10）
- store 35+ 字段过胖：UI（density/leftCollapsed/editingFieldId/locatingTick）+ 领域（ticket/fieldStates/changeLog）+ 异步（queueLoading/error/submitting）耦合一起 → 建议切片
- `confirmField` 无值变更却设 `dirty:true`；`setFieldRemark/toggleUncertain` 设 dirty 但不设 `autoSaveStatus:'saving'`，与其它 action 不一致，加剧 F1 标签失灵
- 选择器基本遵守"不返回新对象"规则（lessons.md 已修复的循环未复发），但 `FieldReviewRow` 订阅整条 changeLog（`FieldReviewRow.tsx:60`）+ 每行 `changeLog.filter()`，30 字段×M 改动 = O(N·M)/keystroke；FieldReviewRow/TicketListItem 均**未 React.memo**

### 新旧割裂（4/10）— 见 F7，第二大风险
- 三套类型并行：`workbench/types.ts` / `api.d.ts`(generated) / `pages/WorkOrderReview/types.ts`
- `api.d.ts` 基本未被消费：`fetchWorkOrder` 返回旧 `WorkOrderData`，converter 形参标 `GeneratedWorkOrderResponse` 靠 `[key:string]:unknown` 索引签名蒙混（typecheck 过但丢类型保护）
- review.ts 手写 `ConfirmRequest` 的 `op:string` 比 generated 的 `'replace'|'add'|'remove'` 更宽
- `submitReview`（旧 ReviewRequest）已被新工作台弃用但仍保留
- antd + @formily/antd-v5 仍打包但新工作台不用，旧页 import antd `message/Drawer/Card`，bundle 虚高，antd CSS-in-JS 与 Tailwind preflight 冲突风险

### 组件设计（7/10）
拆分粒度合理，primitives 抽象到位。核心 UX 逻辑正确：
- "改回原值移除变更"（`setFieldValue:363` + `computeEffectiveChanges:682` 双保险）
- "阻断不可提交"（`selectCanSubmit:713`）
- "定位高亮"（`locatingTick` 递增触发）
但 10 个页面状态散落 `error/ticketLoading/!ticket/queueEmpty/submitDialogOpen/conflict/pendingSwitchId/beingEditedBy/submitting/queueLoading`，建议抽成联合类型 `type ViewState` 便于穷举测试。

### 并发交互（2/10）— 见 F1/F2/F3/F4，最大风险
autoSave/锁/冲突三处交互都是"演"的。

### 类型安全（4/10）
见新旧割裂。`any` 在 mock/converter 中滥用。

### 测试（2/10）
`tests/WorkOrderReview.test.tsx` 只测旧 antd 页，**新工作台 0 单测**。`computeEffectiveChanges/computeBlockingFields/matchFilters` 是纯函数极易测却未覆盖。

### 可访问性（6/10）
用心但有问题：FieldReviewRow 的 DropdownMenu 嵌 Tooltip（`FieldReviewRow.tsx:218-228`）Radix 焦点管理可能冲突；`<kbd>` 未 `aria-hidden`；LeftRail/RightRail 竖排文字无 aria-label 会读两次。

---

## 五、本系统范围内的差距（对照"人工审核 + 销售易对接"目标态）

> 已更正：spec 的 6 大 FR 中，多渠道接入 / AI 身份核验 / AI 智能处理 / 智能派单 / 跨部门协同 / AI 准确性评测由其他系统实现，**不计为本系统差距**。本系统只对照"读共享 DB -> 人工审核 -> 同步销售易"这一段。

| 本系统目标态环节 | 现状 | 差距 |
|---|---|---|
| 读 workorder 表呈现审核 | ⚠️ 后端有读端点，前端纯 mock | 前端未连真实 API；mock 字段模型与真实 DB 不重叠（F7） |
| 人工审核工作台（字段级核对/修改/确认/退回/驳回） | ✅ UI 完成度高，核心交互正确 | 自动暂存不落盘(F1)/锁丢失不阻断(F2)/冲突假合并(F3)/切单竞态(F4) |
| 并发编辑控制 | ⚠️ 有 Redis 锁 + 乐观锁 | 锁非原子(B1)/无越权校验(B7)/与外部系统 version 契约未约定(B9) |
| 字段级审计 + bad case 回流 | ⚠️ 有 audit_log/bad_case 表 | 无 trace_id/模型版本；ai_value 来源假设脆弱(B9.5) |
| **审核通过 -> 同步销售易** | ❌ **空壳**（NotImplementedError + 无字段映射 + 静默 pending） | **系统核心输出无法完成(B8)，最高优先级** |

**本系统范围内的关键缺口（按业务影响排序）**：
1. **销售易对接空壳**（B8）- 系统无法完成唯一业务使命，审核通过后工单不进销售易
2. **共享 DB 集成契约未约定**（B9）- 与外部 AI 系统的 version/status/可见列/读新鲜度契约缺失，审核正确性悬空
3. **并发编辑锁失效**（B1+B7）- 多审核员并发下锁可被误释放、无越权校验
4. **前端持久化/并发交互全是演示态**（F1-F4）- 切真实 API 即丢失修改/误导提交
5. **migration 与 model 不一致**（B2/B3）- 生产首次部署直接失败

**NFR（本系统相关）**：≥10 并发坐席审核、审核操作 P95≤10s、99.9% 可用。当前 SQLite(开发) + 非原子锁 + N+1 写入 + 无索引，生产 MySQL8 + Redis 下仍需压测验证。注：spec 的"≥5 单/秒"指 AI 生成吞吐，不在本系统范围。

**进度风险**：销售易对接（核心输出）尚是空壳，是本系统上线最大的进度瓶颈，需尽快明确销售易 API 文档并实现字段映射与可靠同步。



---

## 六、借鉴开源方案的改进建议（精华）

调研 Label Studio / Prodigy / CVAT / Chatwoot / FreeScout / Yjs / Seldon / Argilla 等后，**最优架构组合**：

1. **数据底座仿 Label Studio**：工单字段拆 `ai_prediction` 与 `human_review` 两套对象，保留原始预测供准确率回溯与训练对齐。当前 WorkOrder 只存当前态，AI 原始值丢失，无法做评测。
2. **字段级乐观锁替代整单锁**：每字段带 `field_version` + 全单 `version`，提交时按字段比对，冲突字段返回 409+最新值，未冲突字段正常落库（部分成功而非整单失败）。解决 B1 整单锁 TOCTOU + F3 假合并。冲突 UX 仿 GitHub 三栏 hunk 取舍，而非整体 409 让用户重填。
3. **编辑锁弱化为"正在编辑"提示**：短 TTL（5min）+ 心跳续约，仅作弱提示不阻塞他人读取其他字段；锁细化到字段区块而非整单。
4. **拉式领取（claim）+ 超时回滚** > 推式 Round-Robin：审核是离散认知型工作，推给离线审核员会堆积；锁定超时自动回队。
5. **置信度驱动三级路由**：高置信自动通过、中置信人审、低置信/abstain 强制人审，由 sampler 决定队列顺序（margin sampling 优先送 top-2 置信度接近的工单），ROI 高于 FIFO。
6. **修改 diff 即训练信号**：reviewer 的 before/after 修正按字段结构化回流（价值高于单纯 reject），配根因分类标签（置信度不足/知识缺失/上下文缺失），分别打不同训练标签。
7. **字段级审计用 JSONB diff + append-only**：主表存当前态、审计表只追加 `{field,before,after,action,operator,role,ts,source(AI/human)}`，回滚=新增反向事件（保证追溯链不断裂），版本对比靠回放两条 audit 记录。
8. **Prodigy 式单手快捷键 + 质量度量**：每字段绑数字键（1 通过/2 改写/3 驳回）+ Enter 提交 + J/K 翻条；注入金标准工单与蜜罐、抽样双复核算 IAA（标注者一致性）。

**不建议照搬**：CRDT/OT（Yjs/Automerge，工单非富文本无实时共编需求）、Label Studio XML 配置体系（字段固定，schema 驱动渲染即可）、整单悲观锁/整单 409、纯事件溯源/CQRS（schema 版本化与 GDPR 难题，append-only 即可）、数据库触发器做审计（跨库难迁移难测试，应在应用层 SA `before_update`/Pydantic diff 实现）、CSAT 当质检（结果指标非过程质检）。

---

## 七、优先级行动计划

### P0（上线阻断，必须修）
1. **B8** 实现销售易同步（HTTP 调用 + 字段映射 + 持久化任务队列 + sync_status 正确流转 + 失败重试与对账 + external_id 回写）--否则系统核心输出无法完成，审核通过工单不进销售易
2. **B9** 与外部 AI 系统对齐共享 DB 契约（version bump 责任 / status='pending_review' 设置方 / 可见列范围 / 变更通知或轮询 / ai_prediction 快照）--否则审核正确性悬空
3. **B1** 锁原子化（Lua 脚本）+ **B7** 入口 acquire 校验--否则并发编辑锁完全失效
4. **B2** migration 补 sync_status + **B3** id 类型统一（与外部系统主键契约对齐）--否则生产首次部署直接失败
5. **B4** JWT_SECRET 启动校验--否则可伪造任意身份
6. **F1** 自动暂存真实落盘 + **F2** 锁丢失强阻塞 + **F3** 冲突真合并 + **F4** 切单竞态保护--否则用户修改丢失/误导提交/切单错乱

### P1（生产质量，强烈建议）
6. **B5/B6** 同步任务持久化与 sync_status 流转（已并入 B8，此处跟踪销售易 HTTP 实现进度）
7. **F7** mock 走 converter 同一路径 + 统一类型到 generated——消除"切 API 工作量被低估"风险
8. **F6** source 筛选修复 + QueueItem 字段补全
9. 后端补并发冲突/审计原子性/锁 TOCTOU 测试；前端补 `computeEffectiveChanges/computeBlockingFields/matchFilters` 纯函数单测 + 新工作台集成测试
10. audit_log 加 trace_id + 模型版本 + 规则版本字段（spec 红线）

### P2（架构演进）
11. 后端读路径抽 `WorkOrderQueryService`，N+1 写入合并
12. 前端 store 切片（UI/领域/异步分离），FieldReviewRow per-field 订阅 + React.memo
13. 移除 antd/@formily 依赖（旧页确认废弃后）
14. 数据底座拆 ai_prediction/human_review（为评测闭环铺路）
15. 字段级乐观锁 + 置信度三级路由 + bad case 结构化回流（对接 spec FR-006 与评测方案）

---

## 八、Review 小结

**资深工程师视角**：这是一个**UI/UX 设计水准远超工程实现水准**的项目。前端三栏工作台的交互设计（阻断定位、改回原值移除变更、10 状态演示、快捷键、自动暂存指示器）体现了对审核场景的深入理解，组件拆分和可访问性也用心。但工程层面，**所有"看不见的正确性"——持久化、并发、冲突、竞态、类型对齐、测试——都停留在演示态**，而本系统的核心输出（销售易同步）目前是空壳，并发与持久化均未达上线标准。

**最需要警惕的认知偏差**：mock 数据 + 流畅 UI 会给团队"已就绪"的错觉。建议在 `tasks/todo.md` 将 P0 六项列为上线前硬阻断（销售易对接为最高优先级），并在切真实 API 前重写异常规则、字段分组、队列摘要映射（F7 工作量被严重低估）。

**建议的下一步**：先明确销售易 API 文档并实现 B8（系统核心输出），同步推进 B9 共享 DB 契约对齐与 B1/B2/B3/B4 后端阻断项，再修前端 F1-F4，最后补测试网与压测。前端连真实 API 前必须先重写异常规则、字段分组、队列摘要映射（F7 工作量被严重低估）。
