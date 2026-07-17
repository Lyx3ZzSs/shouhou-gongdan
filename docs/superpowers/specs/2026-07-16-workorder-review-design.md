# AI 工单审查页面 — 设计方案

> 版本: 1.2 | 日期: 2026-07-16 | 状态: 待实施

## 一、需求概述

AI 引擎生成工单后，将工单呈现在页面中供坐席审查，记录坐席的字段级调整动作（修改了哪个字段、原值→新值、谁改的、何时改的）。审查页是 AI 产出进入派发前的唯一强制人工关卡。

### 核心约束

- 技术栈：React + FastAPI + MySQL 8.0
- 交互模式：单页核对
- 变更追踪：只记录实际修改的字段
- 对比方式：AI 原值 vs 坐席编辑 并排展示
- bad case 回流：实时同步写入

### 安全与认证

- **认证**：所有 API 端点通过 JWT Bearer Token 认证，由 FastAPI 中间件统一校验。身份信息从 token payload 中提取，不可由客户端传入。
- **授权**：采用 RBAC 模型，仅 `customer_service_agent` 角色可调用审查接口。审查范围受部门限制——坐席只能审查分配给本部门的工单。
- **字段白名单**：后端 UPDATE 必须使用显式字段白名单，仅允许坐席可修改的字段（分类、路由、等级、描述等）被更新，禁止覆盖 `created_at`、`status`、`version` 等内部字段。
- **审计身份**：审计日志中的 `operator_id` 和 `operator_name` 从认证中间件注入，禁止客户端传入。

### 验收标准（P3-T04）

1. 工单人工校验页面（AI 工单展示 + 人工核对编辑）
2. 分级分类（三级分类体系可编辑）
3. 优先级标记（P1-P4 + 加急/A类/当日完成标识）
4. 异常工单拦截（缺省份/无分类/无负责人）
5. 退回重填流程（退回 + 重填 + 重新提交闭环）

---

## 二、整体架构

```
┌─────────────────────────────────────────────────┐
│                  坐席工作台 (React)                │
│  ┌───────────────────────────────────────────┐  │
│  │         WorkOrderReviewPage               │  │
│  │  ┌─────────────┐  ┌───────────────────┐  │  │
│  │  │ AI原值面板   │  │  坐席编辑表单      │  │  │
│  │  │ (只读卡片)   │  │  (Formily Schema)  │  │  │
│  │  └─────────────┘  └───────────────────┘  │  │
│  │  ┌──────────────────────────────────┐    │  │
│  │  │  变更预览抽屉 (ChangePreview)     │    │  │
│  │  └──────────────────────────────────┘    │  │
│  │  ┌──────────────────────────────────┐    │  │
│  │  │  异常拦截横幅 (ExceptionAlert)    │    │  │
│  │  └──────────────────────────────────┘    │  │
│  └───────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────┘
                       │ POST /api/workorders/{id}/review
┌──────────────────────┴──────────────────────────┐
│                 FastAPI 后端                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Review   │  │ Audit    │  │ BadCase      │  │
│  │ Service  │  │ Service  │  │ Service      │  │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │             │               │           │
│  ┌────┴─────────────┴───────────────┴────┐      │
│  │              MySQL 8.0                  │      │
│  │  workorders | audit_logs | bad_cases   │      │
│  └────────────────────────────────────────┘      │
└──────────────────────────────────────────────────┘
```

### 前端组件树

```
WorkOrderReviewPage
├── WorkOrderHeader          // 工单流水号、状态标签、AI置信度总览
├── ExceptionAlert           // 异常拦截横幅（缺省份/无分类/无负责人）
├── ReviewLayout (并排)       // 左右两栏
│   ├── AiPreviewPanel       // 左侧：AI 原值（只读卡片）
│   │   ├── FieldGroup "基本信息"
│   │   ├── FieldGroup "分类归属"
│   │   ├── FieldGroup "路由分配"
│   │   └── FieldGroup "时效等级"
│   └── EditFormPanel        // 右侧：坐席编辑表单 (Formily)
│       ├── Tab "基本信息"
│       ├── Tab "分类归属"
│       ├── Tab "路由分配"
│       └── Tab "时效等级"
├── ChangePreviewDrawer      // 提交前变更摘要抽屉
│   └── ChangeItem[]         // 每个修改的字段：字段名 | AI原值→新值
└── ActionBar                // 底部操作栏：确认提交 / 退回重填
```

### 后端模块

```
api/
├── routers/
│   └── review.py            // POST /workorders/{id}/review
│                             // GET  /workorders/{id}/audit-logs
├── services/
│   ├── review_service.py    // 校验 + 更新工单 + 编排审计/bad_case
│   ├── audit_service.py     // 写入审计日志
│   └── bad_case_service.py  // 写入 bad_case 样本
├── models/
│   ├── workorder.py         // 工单模型 (132字段)
│   ├── audit_log.py         // 审计日志模型
│   └── bad_case.py          // bad_case 样本模型
└── schemas/
    ├── review.py            // ReviewRequest / ReviewResponse
    └── audit.py             // AuditLog schema
```

---

## 三、数据模型

### 审计日志表

```sql
CREATE TABLE workorder_audit_log (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    workorder_id    VARCHAR(64) NOT NULL,
    session_id      VARCHAR(64) NOT NULL,
    field_path      VARCHAR(128) NOT NULL,
    field_label     VARCHAR(64) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    change_type     VARCHAR(16) NOT NULL DEFAULT 'replace',
    ai_confidence   DECIMAL(5,4),
    operator_id     VARCHAR(64) NOT NULL,
    operator_name   VARCHAR(64),
    operated_at     DATETIME(3) NOT NULL,
    INDEX idx_workorder (workorder_id),
    INDEX idx_session (session_id),
    INDEX idx_operator (operator_id),
    INDEX idx_operated_at (operated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### bad case 样本表

```sql
CREATE TABLE bad_case_sample (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    workorder_id    VARCHAR(64) NOT NULL,
    audit_log_id    BIGINT NOT NULL,
    field_path      VARCHAR(128) NOT NULL,
    ai_value        TEXT,
    human_value     TEXT,
    ai_confidence   DECIMAL(5,4),
    sample_status   VARCHAR(16) NOT NULL DEFAULT 'pending',
    source          VARCHAR(16) NOT NULL DEFAULT 'review_correction',
    created_at      DATETIME(3) NOT NULL,
    INDEX idx_status (sample_status),
    INDEX idx_workorder (workorder_id),
    FOREIGN KEY (audit_log_id) REFERENCES workorder_audit_log(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 工单表增加字段

```sql
ALTER TABLE workorders ADD COLUMN version INT DEFAULT 1;        -- 乐观锁
ALTER TABLE workorders ADD COLUMN reviewed_at DATETIME(3);         -- 审查时间
ALTER TABLE workorders ADD COLUMN reviewed_by VARCHAR(64);          -- 审查人
ALTER TABLE workorders ADD COLUMN reject_count INT DEFAULT 0;       -- 退回次数
ALTER TABLE workorders ADD COLUMN last_reject_reason TEXT;          -- 上次退回原因
ALTER TABLE workorders ADD COLUMN last_rejected_by VARCHAR(64);     -- 上次退回人
ALTER TABLE workorders ADD COLUMN last_rejected_at DATETIME(3);     -- 上次退回时间
```

---

## 四、API 设计

### POST /api/workorders/{id}/review

```python
class FieldChange(BaseModel):
    op: Literal["replace", "add", "remove"]
    path: str
    field_label: str
    old_value: Any | None
    new_value: Any | None
    ai_confidence: float | None

class ReviewRequest(BaseModel):
    session_id: str            # 幂等键，同一 session_id 的重复提交返回已有结果
    version: int               # 乐观锁版本号
    changes: list[FieldChange] # 仅包含坐席实际修改的字段
    reject_reason: str | None  # 退回重填时必填

class ReviewResponse(BaseModel):
    review_id: str             # 审查记录 ID，用于客户端查询提交状态
    workorder_id: str
    status: Literal["confirmed", "rejected"]
    change_count: int
    bad_case_count: int
    next_status: str
```

**身份注入**：`operator_id` 和 `operator_name` 不在 ReviewRequest 中，由 FastAPI 依赖注入从 JWT token 中提取：

```python
@router.post("/{workorder_id}/review")
async def review_workorder(
    workorder_id: str,
    request: ReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),  # JWT 中间件注入
    db: AsyncSession = Depends(get_db),
):
    service = ReviewService(db)
    return await service.review(
        workorder_id=workorder_id,
        request=request,
        operator_id=current_user.user_id,
        operator_name=current_user.name,
        operator_department=current_user.department,
    )
```

**字段白名单**：后端 UPDATE 只能修改白名单内的字段，其余字段不可被客户端传入：

```python
# 坐席可修改字段白名单（约 25 个字段）
ALLOWED_FIELDS = {
    # 基本信息
    "station_name", "dispatch_name", "project_code", "project_name",
    "project_province", "customer_name", "problem_description", "feedback_channel",
    "product_line", "product_category", "product_type", "customer_level",
    # 分类归属
    "problem_category_l1", "problem_category_l2", "problem_category_l3",
    "order_type", "problem_type", "fault_category", "fault_detail",
    # 路由分配
    "responsible_person", "responsible_department", "primary_department",
    "after_sales_person", "transferred_person", "transferred_department",
    # 时效等级
    "order_level", "fault_level", "onsite_level", "required_solve_time",
}
```

### GET /api/workorders/{id}/audit-logs

返回按 session_id 分组的变更历史列表，前端渲染时间轴。

### Review Service 事务流程

```
BEGIN;
  1. 幂等性检查：SELECT review_id FROM workorder_audit_log WHERE session_id = ? LIMIT 1
     → 若存在，直接返回已有结果（防重复提交）

  2. 乐观锁 + 状态分支：
     -- confirmed 分支
     UPDATE workorders
     SET status = 'confirmed', version = version + 1, reviewed_at = NOW()
     WHERE id = ? AND version = ? AND status = 'pending_review'

     -- rejected 分支（退回重填）
     UPDATE workorders
     SET status = 'pending_review', version = version + 1,
         reject_count = reject_count + 1,
         last_reject_reason = ?, last_rejected_by = ?, last_rejected_at = NOW()
     WHERE id = ? AND version = ? AND status = 'pending_review'

     → 若 rowcount == 0，回滚并返回 409（版本冲突或状态已变更）

  3. 仅更新变更字段（白名单过滤，仅 confirmed 分支执行）：
     UPDATE workorders SET field1 = ?, field2 = ? WHERE id = ?
     → 只更新 changes 中列出的字段，且字段必须在 ALLOWED_FIELDS 白名单内
     → 未变更的字段不受影响，不会出现 100+ 字段被覆盖为 NULL 的问题

  4. INSERT INTO workorder_audit_log (...) VALUES (...)  -- 批量（含 reject 操作）

  5. bad_case 回流（仅 confirmed 分支 + 有实际变更时执行）：
     IF status == 'confirmed' AND len(changes) > 0:
         INSERT INTO bad_case_sample (...) VALUES (...)  -- 批量
     → 退回重填不写入 bad_case（退回不等于 AI 错误）

  6. 释放编辑锁：DELETE FROM redis review_lock:{workorder_id}
COMMIT;
```

**关键设计决策**：
- 不传完整 `workorder` dict，前端只传 `changes` 列表（仅修改过的字段）
- 后端 UPDATE 只更新 `changes` 中的字段，且经过白名单过滤
- 乐观锁在 SQL 层面完成（`WHERE version = ?`），无 TOCTOU 窗口，无线程间锁竞争
- confirm 和 reject 是两个独立 SQL 分支，写入不同的状态和审计信息
- bad_case 仅在 confirmed + 有实际变更时写入

### 异常处理

| 异常 | HTTP | 处理 |
|---|---|---|
| 工单不存在 | 404 | 返回错误信息 |
| 状态不是 pending_review | 409 | 提示已被处理 |
| 版本冲突 | 409 | 提示刷新重试 |
| 重复提交（session_id 已存在） | 409 | 返回已有审查结果 |
| 编辑锁被他人持有 | 423 | 横幅提示"工单正由 XXX 审查中"，表单只读 |
| 必填字段缺失 | 422 | 返回缺失字段列表 |
| 异常工单拦截 | 422 | 返回异常类型 |
| 未认证 | 401 | 要求登录 |
| 无权限（非本部门/非坐席角色） | 403 | 提示无权限 |
| 事务失败 | 500 | 回滚，提示重试 |

---

## 五、前端 Formily Schema

### 分组策略

| 分组 | 必核字段 | 选核字段 | 性质 |
|---|---|---|---|
| 基本信息 | 场站名称、调度名称、项目编号、项目省份、大客户简称、问题描述、反馈渠道 | 产品线、产品类别 | 客户/项目关联 |
| 分类归属 | 问题分类1~3级、受理单类型、问题类型 | 故障分类、故障明细 | 分类准确性 |
| 路由分配 | 问题责任人、责任部门、一级部门、售后责任人 | 移交后责任人/部门 | 派给谁 |
| 时效等级 | 受理单级别、级别 | 故障等级、进场等级、要求解决时间 | 优先级 |

### 关键联动

- 一级分类选择 → 动态加载二级分类 → 动态加载三级分类
- 省份选择 → 动态加载可选责任人列表
- 省份变更 → 触发异常拦截检查（是否有对应负责人）

### 变更捕获

```typescript
form.addEffects('changeTracker', () => {
  onFieldValueChange('*', (field) => {
    const initialValue = initialValues[field.path.toString()]
    const currentValue = field.value
    const actuallyChanged = !isEqual(currentValue, initialValue)

    if (field.modified && actuallyChanged) {
      // 实际值不同于初始值 → 记录变更
      // 使用 upsert：同一字段再次修改时更新 new_value，而非追加重复记录
      changes.current = upsert(changes.current, {
        op: 'replace',
        path: field.path.toString(),
        field_label: field.title,
        old_value: initialValue,
        new_value: currentValue,
        ai_confidence: field.data?.aiConfidence ?? null,
      })
    } else if (field.modified && !actuallyChanged) {
      // 值被改回原始值 → 从变更列表中移除该字段
      changes.current = changes.current.filter(c => c.path !== field.path.toString())
    }
  })
})
```

**假阳性防护**：`field.modified` 在 Formily 中只标记"是否被编辑过"，不会在值被改回原始值后自动恢复。因此必须增加值实际对比 `isEqual(currentValue, initialValue)`：
- 值确实不同 → 记录变更
- 值被改回原始值 → 从变更列表中移除，避免产生 `old_value='数据问题' → new_value='数据问题'` 的虚假记录

---

## 六、页面状态与交互

### 状态机

```
loading → editing → previewing → submitting → success (confirmed)
                 ↘ blocked       (可修正后继续)
                 ↘ rejected      (退回重填 → 回到 pending_review)
submitting → error (提交失败，保留编辑数据，允许重试)
```

### 异常拦截横幅

编辑中实时校验，触发异常时顶部展示拦截横幅，提交按钮置灰。修正后自动解除。

### 变更预览抽屉

提交前展示所有变更的 before/after 摘要，坐席确认后真正提交。

### 提交失败处理

当接口返回非 409 错误（500/超时等）时：
1. 变更预览抽屉关闭，回到编辑页
2. 顶部展示 error toast："提交失败，请重试。如多次失败请联系管理员"
3. 表单数据保留在内存中，坐席可重新提交
4. 重试使用相同的 `session_id`，后端幂等性保证不会重复创建审计记录

### 并排对比交互

- 左侧 AI 原值面板：灰色标签 `AI: xxx`，低置信度(<80%) 红色标记
- 右侧编辑表单：被修改字段高亮黄色边框，hover 显示原值→新值
- 提交前变更抽屉：汇总所有变更，确认后提交

### 并发控制

工单表 `version` 字段实现乐观锁。前端加载时获取 version，提交时回传。版本不匹配返回 409，提示刷新。

### 编辑锁定机制

防止多人同时编辑同一工单导致编辑丢失：

1. **进入编辑时加锁**：坐席打开审查页时，前端调用 `POST /api/workorders/{id}/lock` 获取编辑锁
2. **锁超时**：锁有效期 5 分钟，超时自动释放。前端每 2 分钟发送心跳续期
3. **他人进入提示**：当坐席 B 打开已被坐席 A 锁定的工单时，页面顶部展示横幅："工单正由 XXX 审查中（已编辑 X 分钟）"，表单为只读模式
4. **锁释放**：提交成功 / 退回重填 / 关闭页面（beforeunload）时释放锁
5. **锁实现**：Redis 键 `review_lock:{workorder_id}`，值为 `{operator_id}:{operator_name}:{locked_at}`，TTL 5 分钟

**锁接口安全约束**：

```python
# POST /api/workorders/{id}/lock  — 获取锁
#   → 若锁不存在，创建锁并返回 { locked: true, owner: current_user }
#   → 若锁存在且持有者为 current_user，返回 { locked: true, owner: current_user }（幂等）
#   → 若锁存在且持有者为他人，返回 { locked: false, owner: "张三", locked_minutes: 3 }

# DELETE /api/workorders/{id}/lock  — 释放锁
#   → 必须验证 current_user == lock.owner_id，否则返回 403
#   → 非持有者调用：返回 403 { error: "仅锁持有者可释放" }

# PUT /api/workorders/{id}/lock  — 心跳续期
#   → 必须验证 current_user == lock.owner_id
#   → 验证通过：重置 TTL 为 5 分钟
#   → 验证失败（锁已被他人持有）：返回 423 { error: "编辑锁已被他人获取，请刷新页面" }
#   → 锁已过期不存在：返回 423 { error: "编辑锁已过期，请刷新页面" }
```

### 退回重填流程

坐席点击「退回重填」→ 填写退回原因 → 提交：

```
POST /api/workorders/{id}/review
  { session_id, version, changes: [], reject_reason: "分类与客户描述不符，需重新判定" }
```

后端根据 `reject_reason` 是否为空判断分支：
- `reject_reason` 为 None → confirmed 分支，更新工单字段 + 写 bad_case
- `reject_reason` 有值 → rejected 分支，保持 pending_review + 记录退回原因

后端处理：
1. 工单状态保持 `pending_review`，`reject_count` 自增，记录 `last_reject_reason`、`last_rejected_by`、`last_rejected_at`
2. 记录退回操作到审计日志（change_type: "rejected"）
3. 不做 bad case 回流（退回不等于 AI 错误）
4. 工单回到待审查队列，可被同一或另一坐席重新打开

前端展示退回历史：
- 工单被重新打开时，若 `reject_count > 0`，在页面顶部展示退回横幅：
  "此工单已被退回 {reject_count} 次，上次退回原因：{last_reject_reason}（{last_rejected_by}，{last_rejected_at}）"
- 审计日志中可查询完整退回历史（按时间倒序）

### 只读展示字段

以下字段在 WorkOrderHeader 区域或 AI 原值面板中只读展示，不参与编辑：
- 流水号、发起时间、受理单状态、发起人、发起部门
- 解决方案提交日期、问题解决方案、是否闭环、客户满意度
- AI 置信度总览、AI 建议方案

---

## 七、审查字段范围

### 必核字段（AI 生成 + 高影响）

分类：问题分类/1级/2级/3级、受理单类型、问题类型
关联：场站名称、调度名称、项目编号/名称、项目省份、大客户简称
路由：问题责任人、责任部门、一级部门、售后责任人
等级：受理单级别、级别
描述：问题详细描述、反馈渠道

### 选核字段（二审/按场景）

故障等级/分类/明细、进场等级、客户级别、移交后责任人/部门、产品线/类别/类型