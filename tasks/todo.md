# 工单人工审核工作台 重构计划

> 目标：把当前简单的"列表→详情表单"审核页，重构为面向高频人工审核的专业桌面三栏工作台。
> 技术基底（已与用户确认）：**Tailwind CSS v3 + shadcn/ui 风格**（Radix + CVA + cn）+ lucide-react + zustand。
> 数据：按 spec 要求用**内置 mock 数据**独立可运行，不连后端；旧 antd 审核页与 `api/review.ts` 保留不动。

---

## 0. 关键决策

| 项 | 决策 | 理由 |
|---|---|---|
| 样式基底 | Tailwind v3.4 + shadcn/ui 风格 primitives | 用户确认；对密集自定义布局控制力最强 |
| 图标 | lucide-react | spec 推荐，克制风格，与 shadcn 一致 |
| 状态 | zustand | 大量联动状态（字段/变更/进度/暂存/冲突/快捷键/筛选） |
| 表单 | 不用 Formily；zustand + 受控输入 | "字段审核行=原始值\|当前值\|置信度\|状态\|操作"模型与表单模型不匹配 |
| 数据 | mock 数据，独立可运行 | spec："使用模拟数据展示完整效果" |
| 路由 | App.tsx 直接渲染新 `ReviewWorkbench` | 工作台自带左侧队列，无需独立列表页 |
| 旧代码 | 保留旧 `WorkOrderReview/`（有测试+后端集成），不路由、不删 | 最小影响、可回退 |
| Tailwind preflight | 全局引入；旧 antd 页不再挂载，无实时冲突 | 新工作台为唯一主视图 |

---

## 1. 视觉系统（spec 第九节）

- 中性浅灰背景 `#F5F6F8`，内容区白，分隔线代替阴影，圆角 4-6px，无渐变，无营销风。
- shadcn HSL CSS 变量主题：primary 克制蓝、语义色（success 绿 / warning 橙 / danger 红 / muted 灰）映射到 spec 颜色语义。
- 8px 间距体系。字号：14 常规 / 12 辅助 / 18-20 标题。字段行 44-52px，输入 36-40px，表格行 40-48px，模块间距 16px，页面边距 16-24px。
- 自定义滚动条（细、中性色）。

---

## 2. 数据模型 `workbench/types.ts`

```ts
type FieldReviewStatus = "unchecked" | "confirmed" | "modified"
  | "low_confidence" | "warning" | "blocking_error";
type ReviewDecision = "approved" | "approved_with_changes" | "returned"
  | "rejected" | "transferred" | "draft";
type RiskLevel = "high" | "medium" | "low";
type AnomalyType = "blocking_error" | "warning" | "info" | "system_suggestion";
type FieldGroupId = "basic" | "contact" | "description" | "category"
  | "address" | "requirement" | "attachment" | "system";

interface FieldDef { id; name; group; originalValue; systemSuggestion?;
  confidence?; required?; type: text|select|textarea|number|phone|datetime|tags;
  options?; unit?; isKey?; }
interface FieldState { currentValue; status; remark?; changeReason?; changedAt?; }
interface Anomaly { id; type; fieldId?; message; }
interface ChangeRecord { id; fieldId; fieldName; before; after; reason; timestamp; kind: modify|supplement|reset|confirm; }
interface AuditLogEntry { id; timestamp; category: system|field_change|process|comment|external; actor; action; detail?; }
interface ReviewTicket { id; serialNumber; title; type; urgency; riskLevel; source;
  status; createdAt; slaRemainingMin; systemConfidence; reviewer; beingEditedBy?;
  version; fields: FieldDef[]; anomalies: Anomaly[]; auditLogs: AuditLogEntry[]; }
interface QueueItem { id; serialNumber; title; type; riskLevel; status; anomalyCount;
  slaRemainingMin; createdAt; stashed?; lockedByOther?; hasLowConfidence?; hasValidationError?; modified?; }
interface ConflictInfo { otherUser; theirChanges: {fieldName; before; after}[]; theirVersion; }
type AutoSaveStatus = "idle" | "saving" | "saved" | "failed" | "offline";
```

派生（selector）：审核进度、**有效变更**（字段改回原值则从变更列表移除）、异常清单、阻断错误、`canSubmit`。

---

## 3. mock 数据 `workbench/mock/mockData.ts`

队列：8-10 条工单摘要，覆盖不同状态/风险/SLA/异常数/暂存/被他人编辑。
当前主工单（WO-20260717-0381 设备故障报修）20+ 字段分 8 组，至少含：
- 2 已修改：工单类型(设备异常→设备故障)、所属区域(东京二区→东京一区)
- 1 缺失：联系电话（空→阻断错误）
- 1 低置信度：所属区域 43%
- 1 字段冲突：紧急程度（李四改中→高，用于版本冲突弹窗）
- 1 系统建议值：设备名称（系统建议"XYZ-2000 变频器"）
- 1 阻断错误：联系电话缺失 + 故障等级与描述不一致
- 3+ 历史操作记录（系统生成/开始审核/字段修改）
- 常用备注短语、修改原因 7 项、异常清单、审计时间线

---

## 4. 状态 `workbench/store/useReviewStore.ts`

state：queue / filters / savedViews / selectedId / ticket / fieldStates{} / changes[] / auditLogs[] / notes / autoSaveStatus / conflict / decision / submitDialogOpen / submitting / ui{leftCollapsed,rightCollapsed,fieldFilter,expandedGroups,locatingFieldId,editingFieldId}

actions：selectTicket, setFieldValue(+reason), confirmField, resetField, useSuggestion, undoChange, setFieldRemark, markUncertain, addNote, prevTicket, nextTicket, stash, submit(decision), open/closeSubmitDialog, resolveConflict(merge|discard), toggleLeft/right, setFieldFilter, toggleGroup, jumpToNextAnomaly, locateField, triggerConflictDemo, triggerBeingEditedDemo

---

## 5. 组件清单（严格按 spec 结构）

```
ReviewWorkbench（根布局：顶56固定 + 底操作栏固定 + 三栏 + 主体独立滚动 + 全局键盘/暂存）
├ WorkbenchHeader（产品名/全局搜索/今日进度/通知/用户/队列切换 + 自动暂存指示器）
├ ReviewQueue（300px 可收起）
│  ├ QueueStatistics（待审/即将超时/已暂存/今日已处理）
│  ├ QueueFilters（9 筛选 + 保存视图：我的待审/高风险/即将超时/低置信度/退回重交）
│  ├ TicketList
│  └ TicketListItem（紧凑行：风险/编号/标题/类型/异常数/SLA/创建/暂存/被编辑；克制选中态）
├ ReviewWorkspace（中，min 720，独立滚动）
│  ├ TicketReviewHeader（标题/编号/状态/风险/来源/创建/SLA/置信度/审核人/并发/复制/打开原单/转交/更多）
│  ├ ValidationSummary（阻断/风险/信息/系统建议；可点击定位）
│  ├ ReviewToolbar（全部/只看异常/只看已修改/跳到下一问题）
│  ├ FieldReviewSections
│  ├ FieldGroup（名/字段数/异常数/已修改数/展开收起；无异常默认收起）
│  ├ FieldReviewRow（名/原始值/当前值/置信度/状态/操作：编辑/确认/重置/用建议/撤销/历史/备注/标记不确定）
│  ├ FieldDiff（删除线+浅色高亮，不刺眼）
│  └ FieldEditInline（内联编辑 + 修改原因 7 项选择）
├ ReviewSidebar（340px 可收起，独立滚动）
│  ├ ReviewProgress（8/11 + 已确认/已修改/待异常/未确认关键字段；可点击定位）
│  ├ CurrentChanges（实时：时间/字段/前/后/原因/定位/撤销；改回原值移除）
│  ├ AuditTimeline（系统/字段修改/流程/评论/外部 五类区分）
│  └ ReviewNotes（文本框 + 常用短语）
├ StickyDecisionBar（底固定：左 上一条/下一条/暂存；右 驳回/直接通过/修改后通过/提交并下一条；阻断时禁用通过并提示定位）
├ ReviewSubmitDialog（完整摘要：结论/修改数/每字段前后/已处理异常/未处理问题/备注/原因汇总/提交并下一条）
├ VersionConflictDialog（他人更新/对方修改/使用最新合并/放弃我的/查看双方差异）
└ primitives: StatusBadge / ConfidenceBar / SLACountdown / RiskTag / AutoSaveIndicator
```

shadcn 风格 UI primitives（`components/ui/`）：button, input, textarea, select, badge, dialog, popover, tooltip, dropdown-menu, label, separator（Radix: dialog/popover/tooltip/select/dropdown-menu/slot；其余纯手写）。

---

## 6. 交互与状态（spec 第六/七/八节）

快捷键（`useKeyboardShortcuts`）：J/K 上下条、Enter 确认字段、Cmd/Ctrl+Enter 提交、Cmd/Ctrl+S 暂存、Alt+↓ 下一异常、Esc 关弹窗/退出编辑。
自动暂存（`useAutoSave`）：失焦/停输入1s/切单/定时；状态 saving/saved/failed/offline。
切单前未保存修改 → 确认弹窗。提交成功 → toast + 自动下一条 + 保留筛选。
异常点击 → scrollIntoView + 高亮。字段改回原值 → 从有效变更移除。

**10 个页面状态**演示分布：
1 默认待审核 / 2 多异常 / 3 编辑中 / 4 多项修改 / 5 阻断不可提交 / 6 提交弹窗 / 7 自动暂存成功 → 主工单自然流程
8 被他人编辑 / 9 版本冲突 → 通过"更多操作"菜单的"模拟"项触发（明确标注演示）
10 审核完成自动下一条 → 提交后自动推进

---

## 7. 布局与响应（spec 第十节）

- 顶 56 固定 + 底操作栏固定；三栏；中间主体独立滚动。
- 最小 1280 / 适配 1440 / 1920；左右栏可收起。
- 无障碍：所有表单元素有 label，按钮有 hover/focus/disabled/loading，键盘可达，aria 标注。

---

## 8. 实施步骤（勾选）

- [x] 1. 装依赖 + 配置 Tailwind/postcss/tailwind.config + path 别名(@/) + index.css(shadcn 主题) + lib/utils.ts(cn)
- [x] 2. 写 shadcn 风格 UI primitives（button/input/textarea/select/badge/dialog/popover/tooltip/dropdown-menu/label/separator）
- [x] 3. types.ts + mock/mockData.ts + lib/constants.ts(分组/原因/短语/状态元) + lib/format.ts
- [x] 4. store/useReviewStore.ts（含 selectors）
- [x] 5. primitives（StatusBadge/ConfidenceBar/SLACountdown/RiskTag/AutoSaveIndicator）
- [x] 6. WorkbenchHeader + ReviewQueue 全套（Statistics/Filters/List/ListItem）
- [x] 7. ReviewWorkspace 全套（Header/ValidationSummary/Toolbar/Sections/Group/Row/Diff/EditInline）
- [x] 8. ReviewSidebar 全套（Progress/CurrentChanges/AuditTimeline/Notes）
- [x] 9. StickyDecisionBar
- [x] 10. ReviewSubmitDialog + VersionConflictDialog
- [x] 11. useKeyboardShortcuts + useAutoSave + 切单未保存确认
- [x] 12. ReviewWorkbench 根组合 + App.tsx 接线 + main.tsx 引 index.css
- [x] 13. typecheck + build 通过
- [x] 14. 自查 10 状态/交互/响应式；补 review 小节；更新 lessons.md

---

## 9. Review 小节

### 交付成果

**38 个 workbench 文件** + 11 个 shadcn UI primitives + 4 个配置文件修改，共约 50 个文件变更。

**技术栈：**
- Tailwind CSS v3.4 + PostCSS + shadcn 风格 HSL 主题（Radix: dialog/popover/tooltip/select/dropdown-menu/slot；CVA + clsx + tailwind-merge）
- lucide-react 图标
- zustand 4.5 状态管理（useMemo 稳定派生）
- React 18 + TypeScript 5 + Vite 5

**组件结构（严格按 spec）：**
```
ReviewWorkbench（根：h-screen flex-col + TooltipProvider + 键盘/暂存 hooks）
├ WorkbenchHeader（56px 固定顶：产品名/搜索/今日进度/通知/队列切换/用户/自动暂存指示器）
├ ReviewQueue（300px 可收起→w-12 rail）
│  ├ QueueStatistics（4 统计 2×2 grid）
│  ├ QueueFilters（保存视图 chips + 下拉筛选 + 3 toggle）
│  ├ TicketList / TicketListItem（紧凑行 60px，选中态 primary/5 + 左 accent 条）
├ ReviewWorkspace（flex-1 独立滚动）
│  ├ TicketReviewHeader（标题/编号/状态/风险/来源/SLA/置信度/审核人/并发/更多→演示）
│  ├ ValidationSummary（异常汇总 + 可点击定位 + 已处理标记）
│  ├ ReviewToolbar（3 段筛选 + 跳到下一问题 Alt+↓）
│  ├ FieldGroup（sticky 分组头 + 计数 + 展开收起；无异常默认收起）
│  ├ FieldReviewRow（6 列 grid：名/原始值/当前值/置信度/状态/操作；定位高亮动画）
│  ├ FieldEditInline（内联编辑 + 原因选择 + 确认/取消）
│  └ FieldDiff（删除线→高亮，不刺眼）
├ ReviewSidebar（340px 可收起→w-12 rail）
│  ├ ReviewProgress（进度条 + 4 可点击统计）
│  ├ CurrentChanges（实时变更，useMemo 防循环）
│  ├ AuditTimeline（5 类时间线：system/field_change/process/comment/external）
│  └ ReviewNotes（Textarea + 常用短语 chips）
├ StickyDecisionBar（底固定：左 导航+暂存 ⌘S；右 6 审核结论；阻断→禁用通过+点击定位）
├ ReviewSubmitDialog（完整摘要：修改字段/异常处理/备注/原因汇总/checkbox 下一条）
├ VersionConflictDialog（对方修改/合并/放弃/双方差异对比）
├ UnsavedSwitchDialog（切换丢弃修改确认）
└ SubmittedToast（提交/暂存成功提示，2.6s 自动消失）
```

**数据模型：**
- `FieldReviewStatus` 6 状态 + `ReviewDecision` 6 结论 + `AnomalyType` 4 异常类
- 24 字段 8 分组 + 6 异常 + 7 审计日志 + 8 队列工单
- 主工单预置 2 修改 + 1 缺失阻断 + 1 低置信度 43% + 1 冲突 + 1 系统建议
- 阻断时 `canSubmit=false`：仅 blocking_error 类型在 `status==='modified'` 时解析

**10 个页面状态：**
1. 默认待审核 → 主工单初始状态
2. 多异常 → 6 异常在 ValidationSummary 展示
3. 编辑中 → 点击编辑按钮，FieldEditInline 内联展开
4. 多项修改 → 预置 2 修改 + 右侧 CurrentChanges 实时显示
5. 阻断不可提交 → 联系电话缺失，底部通过按钮禁用 + 点击定位
6. 提交弹窗 → 底部"修改后通过"→ ReviewSubmitDialog 完整摘要
7. 自动暂存 → 编辑后 Header 右上角 AutoSaveIndicator 显示"已自动保存"
8. 被他人编辑 → 更多操作→模拟：被他人编辑（李四编辑中 banner）
9. 版本冲突 → 更多操作→模拟：版本冲突（VersionConflictDialog）
10. 完成进下一条 → 提交 + 勾选"提交并进入下一条"→ 自动推进

### 验证结果

- `npx tsc --noEmit` ✓ 通过
- `npm run build` ✓ 通过（CSS 26KB / JS 403KB gzipped 125KB）
- Dev server 启动 ✓（localhost:5174）
- 运行时 0 报错（修复了 zustand 选择器返回新对象/数组导致无限循环的 2 个 bug）

### 已知局限

- 模拟数据独立可运行，未连接后端（按 spec 要求）；后端 `api/review.ts` 保留
- 旧 `WorkOrderReview/` 页保留（有测试），不再路由
- 演示状态（被他人编辑/版本冲突/保存失败/离线）通过"更多操作→演示"显式触发
- 暂未实现：附件上传、字段修改历史完整持久化、并发编辑真实后端协作
- 宽度 1280 时两侧面板同时打开中间仅 640px（略低于 spec 720px min）；至少收起一侧即可

---

## 9. 验证

- `npm run typecheck` 通过
- `npm run build` 通过
- 人工自查：10 状态、快捷键、自动暂存、冲突弹窗、字段差异、变更实时、阻断禁用通过、提交摘要、1280/1440/1920 响应式、左右收起、无障碍标签

---

## 10. 风险/取舍

- mock 数据独立可运行，不连后端（spec 要求）；旧 `api/review.ts` 保留。
- 旧 `WorkOrderReview/` 保留不删（有测试），仅不再路由。
- 状态8/9 用"更多操作→模拟"显式触发，避免污染默认流程（诚实标注演示）。
- shadcn primitives 手写（=shadcn 本意：组件归你所有），Radix 仅用于 dialog/popover/tooltip/select/dropdown-menu 以保无障碍。

---

## 11. Review 驱动修复 — 第一批（2026-08-05）

三子 Agent 并行 Review（前端交互/后端架构/统计可视化）后按路线图修复的第一批正确性核心问题。

### 已完成

1. **同步早退 failed 落库** `backend/app/services/review_service.py`
   - 记录不存在、ticket_no 不在 v_ticket 的两个早退分支，返回前写 `sync_status='failed' + sync_last_error`，避免工单永久卡 `syncing` 不可见。
2. **驳回重置耗时 + 统计驳回口径修正** `review_service.py` / `stats_service.py` / `frontend/src/stats`
   - `_execute_reject` 置 `review_started_at=NULL, review_duration_seconds=NULL`，二次确认耗时只含第二段。
   - stats 通过按 `reviewed_at`、驳回按 `last_rejected_at` 分别取数 UNION 聚合；状态分布新增"已驳回待返工"切片；overview 新增 `one_pass_rate`（一次通过率）、`total_rejected`，修正 `approval_rate` 分母（已评审而非含未审核）。
3. **前端提交成功回写状态 + 停心跳** `useReviewStore.ts` / `useReviewLock.ts` / `StickyDecisionBar.tsx`
   - submit 成功回写 `ticket.status`（confirmed/rejected）+ version+1，停留页时置 `lockState='released'`；心跳检测到 released/工单切换即停，不再 2 分钟误报锁丢失。
   - `selectCanSubmit` / `setFieldValue` / `resetField` 增加已决策守卫；StickyDecisionBar 显示"已确认提交/已驳回"终态。
4. **409 冲突结构化 + 冲突合并用最新版本** `review_service.py` / `api/review.ts` / `useReviewStore.ts`
   - 409 返回 `{message, version, review_status}`；`ConflictError` 携带二者；merge 分支改用 `latest.version`，工单已被他人确认/驳回时从队列移除并提示。

### 验证

- 后端：`py_compile` + app import OK；脚本级端到端验证 4 项全通过
  - #13 伪造 ticket_no → 同步返回 failed 且落库（此前卡 syncing）✓
  - #14 驳回后 `review_started_at=NULL`、`reject_count=1`，by-reviewer 驳回数可见（此前恒 0）✓
  - #16 错误版本提交 → 409 返回结构化 `{version, review_status}` ✓
  - 新 stats 4 个查询在真实库执行通过 ✓
- 前端：`npx tsc --noEmit` 通过 ✓

### 待办（后续批次）

- 第二/三批：索引与 DDL 权威统一、周期 sweeper、httpx 单例、销售易 idempotencyKey 去重语义确认、SLA/日期解析、统计接口鉴权、错误字段聚合、售后效率趋势面板。

---

## 12. Review 驱动修复 — 第二批（2026-08-05）

性能与可靠性。

### 已完成

5. **补索引 + 统一 DDL 权威** `schema_init.sql` / `init_pg.py` / `README.md`
   - 确认部署路径：`docker compose up` 自动执行 `schema_init.sql`；alembic 为"stamp 标记、从未执行"的遗留（迁移目标还是废弃的 `workorder` 表）。
   - `schema_init.sql` 补齐 workorder_review 全部索引（review_status / review_status+created_at DESC / sync_status / sync_status+reviewed_at / created_at DESC / updated_at / sync_external_id）。
   - 运行库补齐缺失的 3 个索引：idx_review_created_at、idx_review_sync_reviewed、idx_review_sync_external_id（其余已存在）。
   - 统一 DDL 权威：README 标注 schema_init.sql 为唯一权威；`init_pg.py` 标注为遗留脚本并修正误导性的"alembic stamp head"指引。
6. **周期 sweeper 复用原子认领** `main.py` / `review_service.py` / `config.py`
   - lifespan 中新增 `_sweeper_loop` 周期任务，复用 `recover_orphan_syncs`（interval 默认 120s，0 禁用），兜底进程崩溃后 pending 滞留/后台任务丢失。
   - `recover_orphan_syncs` 增加 `per_cycle_cap` 参数（默认 50），防止销售易故障后积压时无界 fan-out。
7. **httpx 客户端改进程级单例** `xiaoshouyi.py` / `review_service.py` / `main.py`
   - `get_xiaoshouyi_client()` 改为进程级单例（共享 httpx 连接池 + token 缓存），新增 `close_xiaoshouyi_client()`。
   - 移除每次同步后的 `client.close()`，改为 shutdown 时统一关闭。
   - 效果：不再每单重取 token（同步从 2 次 HTTP 往返降为 1 次）、复用 TCP/TLS 连接。

### 验证

- `py_compile` + app import + lifespan 启停集成验证通过（sweeper 任务正常创建与取消、Redis/销售易客户端/DB 连接干净关闭）✓
- recover_orphan_syncs 认领 + 30min 防重复认领验证通过 ✓
- 单例客户端：3 次调用同一实例、httpx 连接池共享验证通过 ✓
- 运行库最终 10 个索引（pkey + unique + 8 索引）✓

### 待办（第三批，含需你决策项）

- 销售易 `idempotencyKey__c` 去重语义确认（决定认领条件是否收紧）
- SLA/日期解析修复（前端 `computeSlaMinutes` epoch 秒误解析）
- 统计接口鉴权（`/api/stats/*` 加 require_any_role，需同步改前端带 token）
- 错误字段聚合接口（audit_log.field_path）与售后效率趋势面板

---

## 13. Review 驱动修复 — 第三批（2026-08-05）

数据价值与安全加固。

### 已完成

8. **同步认领条件收紧** `review_service.py`
   - 认领条件由 `(sync_status != 'syncing' OR sync_idempotency_key = :key)` 收紧为 `sync_status != 'syncing'`：已处于 syncing 的行由活跃任务继续 / 30 分钟超时恢复接管，杜绝多 worker 下同 key 并发双发。
   - 注：顺序重试的重复风险（超时后销售易已建单）仍取决于销售易 `idempotencyKey__c` 去重语义，需销售易侧确认。
9. **SLA/日期解析修复** `frontend/.../converters.ts`
   - `computeSlaMinutes` 原先 `parseInt('2026-08-15')=2026` 按 epoch 秒误解析 → SLA 恒为 0。现兼容：纯数字 epoch 秒 / `YYYY-MM-DD`（UTC 零点，与后端 `_normalize_timestamp` 一致）/ `YYYY-MM-DD HH:MM:SS` / ISO 8601。
10. **统计接口鉴权** `routers/stats.py` / `frontend/src/api/stats.ts`
    - `/api/stats/*` 7 个端点全部加 `require_any_role`（原 5 个公开）；前端 `api/stats.ts` 复用 `api/review.ts` 的 `authFetch`（401 自动刷新 token），AUTH_ENABLED=false 时依旧放行。
11. **错误字段聚合接口** `stats_service.py` / `routers/stats.py` / `frontend`
    - 新增 `GET /api/stats/field-corrections`：按 `audit_log.field_label/field_path` 聚合修正频次（真实数据：工单主题 6 次、工单描述 2 次）。
    - 前端"错误字段 Top"横条图展示。
12. **售后效率趋势面板** `stats_service.py` / `routers/stats.py` / `frontend`
    - 新增 `GET /api/stats/efficiency?weeks=`：按确认周聚合 一次通过率 / 平均返工 / 平均修正字段数 / 同步接受率。
    - 前端"售后效率趋势"折线图（一次通过率 + 同步接受率双线）+ 本周返工/修正/单量指标卡；注明同步接受率依赖销售易启用。

### 验证

- 后端：`py_compile` + app import OK；运行中服务 7 个 stats 端点鉴权后正常返回；efficiency 构造数据聚合数学验证通过（一次通过率/同步接受率=100、返工=0、修正=8）✓
- 前端：`npx tsc --noEmit` 通过 ✓
- field-corrections 返回真实修正数据 ✓

### 待办（第四批/需外部确认）

- **销售易 `idempotencyKey__c` 去重语义**：需销售易侧确认同 key 是否返回原 dataId。若不支持去重，顺序重试仍可能重复建单，需引入对账机制。
- bad_case_sample 管道统计（表只写不读，字段聚合已含 audit_log 部分）
- 审核前 vs 审核后对照基线（需上线前数据，当前只能纵向趋势）

---

## 14. 销售易幂等去重语义实证（2026-08-05）

`scripts/test_idempotency_key.py` 对真实 API 实证测试：同一 `idempotencyKey__c` 调用 3 次 `insertServiceCase`。

### 结论：❌ 销售易不去重

| 调用 | key | body | dataId |
|---|---|---|---|
| 1 | 同 K | A | 4442540885476117 |
| 2 | 同 K | A（完全一致） | 4442540885476131（不同）|
| 3 | 同 K | B（name 改） | 4442540821021485 |

同 key + 同 body 也新建工单。`idempotencyKey__c` 仅是透传自定义字段，**不能作为去重依据**。

### 影响与加固

- 原重试逻辑（超时后同 key 重发，最多 3 次）会重复建单。
- **加固 `review_service.py`**：`asyncio.TimeoutError`（wait_for 20s）不再自动重试——超时 = 请求可能已到达销售易并成功建单、仅响应丢失，盲目重试会重复；改为直接标记 `sync_status='failed'` 并提示"工单可能已创建，请核实"。`failed` 状态 sweeper 不认领，仅管理员 `retry` 端点可人工处理。
- 仍安全的重试路径：HTTP 5xx/408/429（服务端明确拒绝，未建单）、Connect/Pool 网络错误（请求未发出）。
- 文档仅有 `insertServiceCase`，无查询/列表接口，暂时无法做"重试前回查"式对账；如需彻底闭环需向销售易申请查询类接口。
- 实证测试在销售易创建了 3 条标记"幂等测试"的测试工单（幂等测试-工单A×2、幂等测试-工单B）。
