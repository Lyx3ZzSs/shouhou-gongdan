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
