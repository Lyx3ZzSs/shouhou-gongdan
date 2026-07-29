# 北森API字段 ↔ 数据库字段映射 深度分析报告

> 分析日期：2026-07-28

---

## 一、数据库实际结构

通过 Python 连接 `psql -h 10.8.2.206 -p 5432 -U postgres -d workorder` 验证，当前数据库中存在以下表：

### 1.1 旧系统表（全部为空表，0 行数据）

| 表名 | 用途 | 行数 |
|------|------|------|
| `ticket` | 工单表（旧） | 0 |
| `project_info` | 项目/客户信息表 | 0 |
| `source_message` | 消息源表 | 0 |
| `ticket_attachment` | 工单附件表 | 0 |
| `wechat_user` | 微信用户表 | 0 |

### 1.2 新系统表（尚未创建）

新 Python 应用（FastAPI）定义的 `workorder`、`workorder_audit_log`、`bad_case_sample`、`workorder_stash` 四张表**尚未在此数据库中创建**（init_pg.py 未执行，或使用了不同的数据库）。

### 1.3 旧系统表结构详情

**ticket 表**（12 列）:
```
id, ticket_no, source_id, create_time, order_level, status,
project_info_id, problem_description, feedback_channel,
feedback_contact, problem_owner, problem_level1, problem_level2
```

**project_info 表**（25 列）:
```
id, station_name, group_shareholder, project_no, project_no_old,
acceptance_department, product_line, product_catalog,
customer_abbreviation, service_start_time, software_warranty_month,
arrears_days, offline_apply, dispatch_name, customer_level,
project_name, project_name_old, sales, province, contract_party,
service_status, service_end_time, hardware_warranty_month,
leave_date, overdue_service
```

---

## 二、销售易 API 请求参数（34 个字段）

销售易 `POST /openapi/insertServiceCase` 接口需要以下字段：

| # | 参数名 | 类型 | 必填 | 说明 |
|---|--------|------|------|------|
| 1 | ownerId | string | 是 | 北森员工编码 |
| 2 | dimDepart | string | 是 | 北森部门编码 |
| 3 | entityType | string | 是 | 固定值 11010045500001 |
| 4 | name | string | 是 | 工单主题 |
| 5 | caseSource | string | 是 | 工单来源（1-99，9个选项） |
| 6 | feedbackChannel__c | string | 是 | 反馈渠道（1-18，18个选项） |
| 7 | workOrderStatus__c | string | 是 | 工单类型（1-13，13个选项） |
| 8 | caseDescription | string | 是 | 工单描述 |
| 9 | caseStatus | string | 是 | 工单状态（1-6） |
| 10 | caseAccountId | string | 是 | 场站编号 |
| 11 | custLevel1__c | string | 是 | 客户级别 |
| 12 | projectName__c | string | 是 | 项目名称 |
| 13 | projectProvince__c | string | 是 | 项目省份 |
| 14 | bigCustShortName__c | string | 是 | 大客户简称 |
| 15 | serviceCycleStart__c | string | 是 | 服务开始时间戳 |
| 16 | serviceCycleEnd__c | string | 是 | 服务结束时间戳 |
| 17 | isOfflineApply__c | string | 是 | 是否线下申请（1/2） |
| 18 | isOverdueService__c | string | 是 | 是否超期服务（1/2） |
| 19 | problemLevel__c | string | 是 | 问题等级（1/2） |
| 20 | problemType1__c | string | 是 | 问题分类1级（1-6） |
| 21 | problemType2__c | string | 是 | 问题分类2级（1-42） |
| 22 | problemType3__c | string | 是 | 问题分类3级（1-89） |
| 23 | feedbackCount__c | string | 是 | 反馈次数 |
| 24 | problemResponsible__c | string | 是 | 问题责任人（员工编码） |
| 25 | problemDept__c | string | 是 | 问题责任部门 |
| 26 | feedbackUserName__c | string | 是 | 反馈人姓名 |
| 27 | feedbackUserContact__c | string | 是 | 反馈人联系方式 |
| 28 | needCallBack__c | string | 是 | 是否要求回电话（1/2） |
| 29 | isHandled__c | string | 是 | 是否处理（1/2） |
| 30 | needOnSite__c | string | 是 | 是否要求进场（1/2） |
| 31 | remark__c | string | 是 | 备注 |
| 32 | planFeedbackTime__c | string | 是 | 方案反馈时间戳 |
| 33 | requireSolveTime__c | string | 是 | 要求解决时间戳 |
| 34 | defectFlag__c | string | 是 | 缺陷标记 |

---

## 三、逐字段映射正确性评估

### 评估标准
- ✅ **正确**：映射字段在数据库中存在，语义匹配
- ⚠️ **有问题**：映射逻辑有偏差，或目标列不存在但文档处理合理
- ❌ **严重错误**：映射到错误的列、两个字段冲突、或关键字段无存储位置

### 3.1 映射到 ticket 表的字段

| # | 北森字段 | 文档目标列 | 实际 ticket 列 | 评估 | 问题描述 |
|---|---------|-----------|---------------|------|---------|
| 5 | caseSource | ticket.feedback_channel | ✅ feedback_channel 存在 | ⚠️ | 与 #6 共用同一列，值来源不同 |
| 6 | feedbackChannel__c | ticket.feedback_channel | ✅ feedback_channel 存在 | ⚠️ | 与 #5 共用同一列，两个不同概念写同一位置 |
| **7** | **workOrderStatus__c** | **ticket.order_level** | ✅ order_level 存在 | **❌** | **严重：与 #19 冲突！** |
| 8 | caseDescription | ticket.problem_description | ✅ problem_description 存在 | ✅ | 正确 |
| 9 | caseStatus | 默认：待处理 | ✅ status 默认'待处理' | ✅ | 正确 |
| **19** | **problemLevel__c** | **ticket.order_level** | ✅ order_level 存在 | **❌** | **严重：与 #7 冲突！** |
| 20 | problemType1__c | ticket.problem_level1 | ✅ problem_level1 存在 | ✅ | 正确 |
| 21 | problemType2__c | ticket.problem_level2 | ✅ problem_level2 存在 | ✅ | 正确 |
| 24 | problemResponsible__c | ticket.problem_owner | ✅ problem_owner 存在 | ✅ | 正确 |
| 27 | feedbackUserContact__c | ticket.feedback_contact | ✅ feedback_contact 存在 | ✅ | 正确 |
| 26 | feedbackUserName__c | ticket.feedback_user_name | ❌ **不存在** | ❌ | ticket 表中没有此列 |

### 3.2 映射到 project_info 表的字段

| # | 北森字段 | 文档目标列 | 实际 project_info 列 | 评估 | 问题描述 |
|---|---------|-----------|---------------------|------|---------|
| 10 | caseAccountId | project_info.project_no | ✅ project_no 存在 | ✅ | 正确 |
| 11 | custLevel1__c | project_info.customer_level | ✅ customer_level 存在 | ✅ | 正确 |
| 12 | projectName__c | project_info.project_name | ✅ project_name 存在 | ✅ | 正确 |
| 13 | projectProvince__c | project_info.province | ✅ province 存在 | ✅ | 正确 |
| 14 | bigCustShortName__c | project_info.customer_abbreviation | ✅ customer_abbreviation 存在 | ✅ | 正确 |
| 15 | serviceCycleStart__c | project_info.service_start_time | ✅ service_start_time(DateTime) | ✅ | 正确 |
| 16 | serviceCycleEnd__c | project_info.service_end_time | ✅ service_end_time(DateTime) | ✅ | 正确 |
| 17 | isOfflineApply__c | project_info.offline_apply | ✅ offline_apply(Boolean) | ✅ | 正确 |
| 18 | isOverdueService__c | project_info.overdue_service | ✅ overdue_service(Boolean) | ✅ | 正确 |

### 3.3 无存储位置的字段（ticket 表中缺失）

| # | 北森字段 | 文档处理 | 评估 | 问题描述 |
|---|---------|---------|------|---------|
| 1 | ownerId | 目标表为空 | ❌ | 销售易必填字段，ticket 无此列 |
| 2 | dimDepart | 目标表为空 | ❌ | 销售易必填字段，ticket 无此列 |
| 3 | entityType | 目标表为空 | ❌ | 销售易必填字段，默认值 11010045500001 |
| 4 | name | "默认：售后单" | ❌ | 销售易必填字段（工单主题），ticket 无此列 |
| 22 | problemType3__c | 默认：空值 | ⚠️ | ticket 无此列，但销售易此项也是必填 |
| 23 | feedbackCount__c | 默认：1 | ⚠️ | ticket 无此列，用硬编码默认值 |
| 25 | problemDept__c | 根据售后负责人从CRM选择 | ⚠️ | ticket 无此列，需外部获取 |
| 28 | needCallBack__c | 默认：1 | ⚠️ | ticket 无此列，硬编码 |
| 29 | isHandled__c | 默认：2 | ⚠️ | ticket 无此列，硬编码 |
| 30 | needOnSite__c | 默认：2 | ⚠️ | ticket 无此列，硬编码 |
| 31 | remark__c | 空字符串 | ⚠️ | ticket 无此列，硬编码 |
| 32 | planFeedbackTime__c | datetime.now() | ⚠️ | ticket 无此列，硬编码当前时间 |
| 33 | requireSolveTime__c | datetime.now() | ⚠️ | ticket 无此列，硬编码当前时间 |
| 34 | defectFlag__c | 默认：1 | ⚠️ | ticket 无此列，硬编码 |

---

## 四、核心问题汇总

### 🔴 P0 — 致命缺陷

#### 1. **列冲突：workOrderStatus__c 和 problemLevel__c 映射到同一列**（#7 和 #19）

```
workOrderStatus__c (工单类型) ──→ ticket.order_level
problemLevel__c     (问题等级) ──→ ticket.order_level  ← 冲突！
```

- **工单类型**有 13 个选项：售后单(1)、投诉单(2)、A类售后单(3)...专项整改(13)
- **问题等级**只有 2 个选项：常规问题(1)、重要紧急(2)
- 这两个是完全不同的业务概念，写入同一列会互相覆盖，先写的值被后写的覆盖

#### 2. **caseSource 和 feedbackChannel__c 映射到同一列**（#5 和 #6）

```
caseSource         (工单来源) ──→ ticket.feedback_channel
feedbackChannel__c (反馈渠道) ──→ ticket.feedback_channel  ← 冲突！
```

- **工单来源**有 9 个选项：语音(1)、小组件(2)、留言(3)...微信小程序(99)
- **反馈渠道**有 18 个选项：400电话(1)、企微助手(2)...替换会议(18)
- 虽然概念相近，但取值空间不同，写入同一列会丢失信息

### 🟠 P1 — 严重缺失

#### 3. **8 个销售易必填字段在 ticket 表中完全无存储位置**：

| 缺失字段 | 销售易要求 | 文档处理方式 |
|---------|-----------|------------|
| ownerId | **必填** | 目标列为空 |
| dimDepart | **必填** | 目标列为空 |
| entityType | **必填**（固定值） | 目标列为空（可用默认值） |
| name | **必填**（工单主题） | 写死为"售后单" |
| feedbackUserName__c | **必填** | 文档说有此列，实际不存在 |
| needCallBack__c | **必填** | 硬编码默认值 1 |
| isHandled__c | **必填** | 硬编码默认值 2 |
| needOnSite__c | **必填** | 硬编码默认值 2 |

这些字段如果硬编码默认值发往销售易，会导致销售易侧的工单数据不准确。

#### 4. **feedbackUserName__c 映射错误**

文档声称映射到 `ticket.feedback_user_name`，但实际 ticket 表中**不存在**此列。ticket 表的完整列清单中没有 `feedback_user_name`。

### 🟡 P2 — 设计缺陷

#### 5. **时间字段处理不当**（#32, #33）

`planFeedbackTime__c` 和 `requireSolveTime__c` 在文档中写为 `datetime.now()`，意味着每次都是"当前时间"，这不合理——这两个字段在销售易 API 文档中是时间戳类型，应该来自上游数据。

#### 6. **备注字段丢失**（#31）

`remark__c` 被映射为空字符串，任何备注信息都会丢失。

#### 7. **三个时间戳字段存储类型不一致**

- `serviceCycleStart__c` / `serviceCycleEnd__c` → `project_info.service_start_time/service_end_time`（DateTime，正确）
- `planFeedbackTime__c` / `requireSolveTime__c` → 硬编码 `datetime.now()`（不合逻辑）
- 新系统 workorder 表中全部存为 VARCHAR(32)（字符串）

### 🟢 P3 — 轻微问题

#### 8. **文档中多个字段的"示例值"为"文本类型"**

这是占位符文本，不是真实示例值，降低了文档的可读性。

#### 9. **转换规则未在旧系统中实现**

文档描述的时间戳转换（`datetime.fromtimestamp()`）和布尔值转换（1→true, 2→false）只存在于文档中，旧系统 ticket/project_info 表使用了正确的数据类型（DateTime、Boolean），但新系统 workorder 表全部存储为字符串。

---

## 五、新系统（workorder 表）的设计分析

### 5.1 新系统的设计选择

新系统（FastAPI 应用）采用了一个不同的架构：

- **数据库列名 = 销售易 API 字段名**（如 `ownerId`、`caseSource`、`feedbackChannel__c`）
- **单表设计**：所有 34 个销售易字段 + 审核元数据全部在一个 `workorder` 表中
- **直通模式**：sync 时直接从数据库行映射到 API JSON，零转换

### 5.2 新系统的优势

1. **消除了映射冲突**：每个销售易字段有独立列，不再有两个字段共用一列的问题
2. **零转换开销**：不需要字段名映射、类型转换
3. **完整性**：所有 34 个销售易 API 字段都有存储位置（+ `relatedAttachment__c`）

### 5.3 新系统的问题

1. **所有字段存储为字符串**：时间戳、布尔值全部是 VARCHAR，不做类型校验
2. **丢失了旧系统的关联设计**：project_info 的项目/客户信息独立管理的好处消失了
3. **表尚未创建**：init_pg.py 定义的 workorder 表未在此数据库中执行

---

## 六、结论与建议

### 6.1 映射文档评估结论

**该映射文档存在严重错误，不能直接用于生产环境。** 主要问题：

| 严重级别 | 数量 | 说明 |
|---------|------|------|
| 🔴 P0 致命 | 2 | workOrderStatus__c/problemLevel__c 列冲突；caseSource/feedbackChannel__c 列冲突 |
| 🟠 P1 严重 | 2 | 8个必填字段无存储；feedbackUserName__c 映射到不存在的列 |
| 🟡 P2 设计缺陷 | 3 | 时间字段硬编码；备注丢失；类型不一致 |
| 🟢 P3 轻微 | 2 | 示例值占位；转换规则未落地 |

### 6.2 建议

1. **如果使用旧系统（ticket + project_info）**：
   - 必须在 ticket 表中新增至少 14 个列来存储缺失的销售易字段
   - 必须解决 workOrderStatus__c 和 problemLevel__c 的列冲突（拆分 order_level 为两列）
   - 必须解决 caseSource 和 feedbackChannel__c 的列冲突（拆分 feedback_channel 为两列）
   - 重写映射文档，与真实数据库结构对齐

2. **如果使用新系统（workorder 表）**：
   - 执行 `python init_pg.py` 创建 workorder 表
   - 新系统的列名与销售易 API 字段名一致，不需要这篇映射文档
   - 但应该将关键字段（时间戳、布尔值）改为正确的 PG 数据类型

3. **该映射文档需要完全重写**，无论选择哪个方案。

---

## 七、新旧系统对比一览

| 维度 | 旧系统 (ticket + project_info) | 新系统 (workorder) |
|------|-------------------------------|-------------------|
| 表数量 | 2 张业务表 + 3 张辅助表 | 1 张业务表 + 3 张辅助表 |
| 销售易字段覆盖率 | ~22/34 (65%) | 34/34 (100%) |
| 列名风格 | 蛇形命名（problem_description） | 驼峰命名（caseDescription） |
| 映射方式 | 北森字段 → 业务列名（需转换） | 北森字段 = 列名（零转换） |
| 数据状态 | 空表（0行） | 表尚未创建 |
| 适用场景 | 原工单自动生成系统 | 新售后工单审核系统 |
