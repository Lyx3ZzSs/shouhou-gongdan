# Lessons Learned

## 1. zustand 选择器不能返回新对象/数组（否则无限循环）

**问题：** 在 zustand 的 `useReviewStore((s) => ...)` 选择器中，直接返回 `.filter()` / `.map()` 生成的新数组或新对象，每次渲染返回不同引用，导致 `useSyncExternalStore` 检测到 snapshot 变化→重新渲染→无限循环。

**症状：** React 告警 "The result of getSnapshot should be cached to avoid an infinite loop" + "Maximum update depth exceeded"。

**修复：**
- 选择器只返回稳定引用（store 中的原始 state 引用，如 `ticket`、`fieldStates` 等）。
- 派生数据（`effectiveChanges`、`blockingFields`）改为：先选择诸稳定输入，再在 hook 内用 `useMemo` 计算。
- `useShallow` 只在数组元素为**相同引用**时有效；对新对象的数组无效。

**代码模式（正确）：**
```ts
export const useEffectiveChanges = () => {
  const ticket = useReviewStore((s) => s.ticket);
  const fieldStates = useReviewStore((s) => s.fieldStates);
  const changeLog = useReviewStore((s) => s.changeLog);
  return useMemo(
    () => computeEffectiveChanges(ticket, fieldStates, changeLog),
    [ticket, fieldStates, changeLog],
  );
};
```

**代码模式（错误）：**
```ts
// ❌ 每次返回新数组，触发无限循环
export const useEffectiveChanges = () => useReviewStore(useShallow(selectEffectiveChanges));
// selectEffectiveChanges 创建新对象数组，useShallow 浅比较失败
```

## 2. package.json type:module 时 .js 配置需用 ESM 或 .cjs

**问题：** 项目 `package.json` 有 `"type": "module"`，`tailwind.config.js` 和 `postcss.config.js` 用 `module.exports`（CJS）→ Node 报错 "module is not defined in ES module scope"。

**修复：** 将配置文件重命名为 `.cjs`（`tailwind.config.cjs`、`postcss.config.cjs`）。Tailwind v3 和 PostCSS 均支持 `.cjs` 扩展名，且 CJS 互操作最稳。

**备选：** 转换为 ESM 语法（`export default` + `import`），但 `.cjs` 更稳定。

## 3. 组件内联选择器 antd/zustand 混用风险

**问题：** 旧项目使用 antd v5 + Formily，新工作台使用 Tailwind + shadcn。两套设计系统在同一个项目中：Tailwind 的 preflight（CSS reset）会影响 antd 组件样式。

**处置：** 保持旧 antd 审核页不挂载（App.tsx 直接渲染新工作台），Tailwind preflight 仅影响新页面。旧页面代码保留但不路由，避免双系统实时冲突。

**后续：** 若需要同时挂载两套 UI，需考虑 Tailwind `preflight: false` 或 CSS 作用域隔离。

## 4. 企业级后台：信息密度优先的视觉执行

**关键原则：**
- 分隔线 > 阴影：`border-b border-border` 代替 `shadow-sm`，更克制。
- 中性灰色背景 `--app: 220 20% 97%`（#F5F6F8），白色内容区。
- 8px 间距体系：`gap-2`、`px-4`、`py-2` 等。
- 底色 + 少量 Primary 强调 ≥ 大面积高饱和色。
- shadcn 的 HSL CSS 变量体系天然支持语义化颜色（primary/success/warning/destructive/muted），且全局可调。

## 5. 子代理委托：接口契约先于并行

**实践：** 将左侧队列和右侧控制台委托给两个子代理并行开发，中间审核区自己写。成功的前提是**先锁定 store API、types、primitives 和 UI conventions**，子代理拿到的是稳定的契约而非猜测。

**教训：** 子代理产出的 CurrentChanges 中出现了与我相同的 zustand 选择器循环 bug（`useEffectiveChanges` 用 `useShallow` 但返回新对象），证明同一份 conventions 不足以防止所有实现错误——需要更严格的模板或类型化约束。

## 6. Review 前先确认系统边界，不要拿整份 spec 当差距基线

**问题：** 项目仓库是更大平台（spec SRS V0.2 定义 6 大 FR）的一个子系统，只负责"人工审核"环节（外部系统生成工单写入 DB -> 本系统读 DB 呈现 -> 人工审核 -> 通过则 API 同步销售易）。第一版 Review 直接拿整份 spec 当对照基线，把"未实现多渠道接入/AI 核验/智能派单/跨部门协同/评测红线"当成差距，被用户纠正：这些**不在本系统范围**，是 intended scope 不是 gap。

**Why：** 错误的基线会产出误导性结论--把"本不该做的事没做"当成缺陷，既浪费注意力，又稀释真正的风险（销售易对接这个真正的核心输出反而被当成边缘功能轻描淡写）。

**How to apply：**
- Review 前**先问清楚系统边界**：输入从哪来（本例是共享 DB，由外部 AI 系统写入）、输出到哪去（本例是销售易 API）、本系统负责哪一段。把这三点钉死再开始评。
- spec 覆盖范围 > 子系统范围时，只对照"本子系统对应的那一段 spec"找差距，其余当作"上下文"而非"待办"。
- 边界澄清会改变严重性排序：**系统的核心输出路径（本例销售易同步）即使代码量小，也是最高优先级**；占位实现（`raise NotImplementedError` + 静默跳过）在核心路径上 = 系统无法完成使命，是 P0 而非"待实现"。
- 共享数据库集成（外部系统写、本系统读改写同一张表）要专门审：version 字段谁 bump、状态流转谁负责、本系统未建模的列（本例 132 列只建模 35 列）是否影响审核正确性、读新鲜度如何保证。