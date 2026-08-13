"""
测试数据种子脚本 — 为审核功能生成真实的工单测试数据。

用法:
  cd backend && source .venv/bin/activate && python scripts/seed_test_data.py

功能:
  1. 创建源数据表（public）
  2. 创建 ticket_view 视图
  3. 插入 20+ 条真实场景的 ticket 数据
  4. 幂等导入到 workorder_review
  5. 为部分工单设置不同的审核状态（已通过/驳回/暂存/同步失败等）
  6. 生成审核日志和坏例样本数据

审核状态覆盖:
  - pending_review (8条): 待审核的新工单
  - confirmed (5条): 已审核通过
  - pending_review + reject_history (3条): 曾被驳回，重新待审核
  - stashed (1条): 审核进度已暂存
  - confirmed + sync_failed (2条): 已通过但销售易同步失败
  - confirmed + synced (1条): 已通过且已同步到销售易
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings

# ── 配置 ──────────────────────────────────────────────
PREFIX = "wo-"  # workorder id 前缀

# 审核人信息
REVIEWERS = [
    {"id": "user-zhangsan", "name": "张三", "dept": "售后服务部"},
    {"id": "user-lisi", "name": "李四", "dept": "技术部"},
    {"id": "user-wangwu", "name": "王五", "dept": "数据中心"},
]

# ── 工单业务数据 ──────────────────────────────────────
# 20 条真实场景工单，覆盖不同的项目、客户、问题类型
TICKETS = [
    {
        "ticket_no": "SRV-2026-0001",
        "name": "华能阜新风电场功率预测精度下降问题",
        "ownerId": "EMP000101",
        "dimDepart": "售后服务部",
        "caseSource": "1",  # 语音
        "feedbackChannel__c": "1",  # 400电话
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "华能阜新风电场1号机组近一周功率预测精度持续下降，平均偏差超过15%，需要排查预测模型和气象数据源。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "1",  # 现场问题
        "problemType2__c": "2",  # 硬件故障/更换
        "problemType3__c": "23",  # 设备质量问题
        "problemResponsible__c": "张工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "陈站长",
        "feedbackUserContact__c": "13800138001",
        "feedbackCount__c": "3",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "1",
        "remark__c": "客户多次来电催促，要求本周内给出解决方案",
        "planFeedbackTime__c": "2026-08-05",
        "requireSolveTime__c": "2026-08-15",
        "defectFlag__c": "1",
        # project_info 字段
        "caseAccountId": "STN-FX-001",
        "custLevel1__c": "A",
        "projectName__c": "华能阜新风电功率预测项目",
        "projectProvince__c": "辽宁省",
        "bigCustShortName__c": "华能集团",
        "serviceCycleStart__c": "2025-01-01",
        "serviceCycleEnd__c": "2026-12-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "陈站长",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0002",
        "name": "中广核敦煌光伏电站数据采集异常",
        "ownerId": "EMP000102",
        "dimDepart": "运维部",
        "caseSource": "2",  # 小组件
        "feedbackChannel__c": "2",  # 企微助手
        "workOrderStatus__c": "2",  # 投诉单
        "caseDescription": "敦煌光伏电站三区逆变器数据从7月25日起停止上传，现场检查通讯设备正常但服务器端收不到数据包。",
        "caseStatus": "3",  # 处理中
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "2",  # 数据优化
        "problemType2__c": "5",  # 数据采集
        "problemType3__c": "19",  # 现场数据采集异常
        "problemResponsible__c": "李工",
        "problemDept__c": "数据中心",
        "feedbackUserName__c": "王运维",
        "feedbackUserContact__c": "13900139002",
        "feedbackCount__c": "1",
        "needCallBack__c": "1",
        "isHandled__c": "1",
        "needOnSite__c": "2",
        "remark__c": "已远程排查过通讯链路，初步判断是采集终端配置问题",
        "planFeedbackTime__c": "2026-08-02",
        "requireSolveTime__c": "2026-08-10",
        "defectFlag__c": "1",
        "caseAccountId": "STN-DH-002",
        "custLevel1__c": "B",
        "projectName__c": "中广核敦煌100MW光伏项目",
        "projectProvince__c": "甘肃省",
        "bigCustShortName__c": "中广核",
        "serviceCycleStart__c": "2025-06-01",
        "serviceCycleEnd__c": "2027-05-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "王运维",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0003",
        "name": "国电投青海共和风场AGC考核争议",
        "ownerId": "EMP000103",
        "dimDepart": "技术部",
        "caseSource": "3",  # 留言
        "feedbackChannel__c": "3",  # 微信客服
        "workOrderStatus__c": "3",  # A类售后单
        "caseDescription": "青海共和风场上月AGC考核结果存在争议，调度侧记录的调节速率与场站侧记录不一致，需要出具AGC考核分析报告。",
        "caseStatus": "1",  # 待分配
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "3",  # 报告/回函
        "problemType2__c": "9",  # AGC考核分析
        "problemType3__c": "50",  # AGC报告
        "problemResponsible__c": "赵工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "刘经理",
        "feedbackUserContact__c": "13700137003",
        "feedbackCount__c": "2",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "客户要求5个工作日内出具分析报告",
        "planFeedbackTime__c": "2026-08-06",
        "requireSolveTime__c": "2026-08-20",
        "defectFlag__c": "1",
        "caseAccountId": "STN-GH-003",
        "custLevel1__c": "A",
        "projectName__c": "国电投青海共和200MW风电项目",
        "projectProvince__c": "青海省",
        "bigCustShortName__c": "国电投",
        "serviceCycleStart__c": "2024-09-01",
        "serviceCycleEnd__c": "2026-08-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "1",
        "initiator": "刘经理",
        "initiator_dept": "运营部",
    },
    {
        "ticket_no": "SRV-2026-0004",
        "name": "华电宁夏灵武光伏电站逆变器故障",
        "ownerId": "EMP000104",
        "dimDepart": "工程运维部",
        "caseSource": "4",  # 意见反馈
        "feedbackChannel__c": "4",  # 销售部
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "灵武光伏电站5号逆变器频繁报过温故障，7月份已累计停机12次，影响发电量约50MWh。需安排现场排查并更换故障部件。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "1",  # 现场问题
        "problemType2__c": "2",  # 硬件故障/更换
        "problemType3__c": "7",  # 保期内维修
        "problemResponsible__c": "孙工",
        "problemDept__c": "工程运维部",
        "feedbackUserName__c": "周场长",
        "feedbackUserContact__c": "13600136004",
        "feedbackCount__c": "5",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "1",
        "remark__c": "设备仍在保期内，需协调供应商尽快更换",
        "planFeedbackTime__c": "2026-08-01",
        "requireSolveTime__c": "2026-08-08",
        "defectFlag__c": "1",
        "caseAccountId": "STN-LW-004",
        "custLevel1__c": "B",
        "projectName__c": "华电宁夏灵武150MW光伏项目",
        "projectProvince__c": "宁夏回族自治区",
        "bigCustShortName__c": "华电集团",
        "serviceCycleStart__c": "2025-03-01",
        "serviceCycleEnd__c": "2027-02-28",
        "isOfflineApply__c": "1",
        "isOverdueService__c": "2",
        "initiator": "周场长",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0005",
        "name": "大唐内蒙古赤峰风场测风塔数据异常",
        "ownerId": "EMP000105",
        "dimDepart": "工程运维部",
        "caseSource": "5",  # 其他
        "feedbackChannel__c": "5",  # 企微群
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "赤峰风场3号测风塔70m层风速数据持续偏低，与周边测风塔对比偏差超过30%。需要排查是传感器故障还是安装问题。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "1",  # 现场问题
        "problemType2__c": "2",  # 硬件故障/更换
        "problemType3__c": "13",  # 巡检
        "problemResponsible__c": "钱工",
        "problemDept__c": "工程运维部",
        "feedbackUserName__c": "吴主管",
        "feedbackUserContact__c": "13500135005",
        "feedbackCount__c": "1",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "1",
        "remark__c": "",
        "planFeedbackTime__c": "2026-08-10",
        "requireSolveTime__c": "2026-08-25",
        "defectFlag__c": "1",
        "caseAccountId": "STN-CF-005",
        "custLevel1__c": "C",
        "projectName__c": "大唐赤峰100MW风电项目",
        "projectProvince__c": "内蒙古自治区",
        "bigCustShortName__c": "大唐集团",
        "serviceCycleStart__c": "2025-07-01",
        "serviceCycleEnd__c": "2027-06-30",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "吴主管",
        "initiator_dept": "技术部",
    },
    {
        "ticket_no": "SRV-2026-0006",
        "name": "中节能新疆哈密风场短期预测模型优化",
        "ownerId": "EMP000106",
        "dimDepart": "技术部",
        "caseSource": "6",  # 微信公众号
        "feedbackChannel__c": "6",  # 微信
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "哈密风场短期预测（0-4h）准确率近两个月持续低于85%，低于合同中约定的90%标准。需要分析原因并进行模型优化。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "2",  # 数据优化
        "problemType2__c": "1",  # 系统问题
        "problemType3__c": "46",  # 短期/超短期/中期
        "problemResponsible__c": "郑工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "冯主任",
        "feedbackUserContact__c": "13400134006",
        "feedbackCount__c": "4",
        "needCallBack__c": "1",
        "isHandled__c": "1",
        "needOnSite__c": "2",
        "remark__c": "合同约定的准确率KPI为90%，当前只有83%，客户已发函要求整改",
        "planFeedbackTime__c": "2026-08-03",
        "requireSolveTime__c": "2026-08-12",
        "defectFlag__c": "1",
        "caseAccountId": "STN-HM-006",
        "custLevel1__c": "A",
        "projectName__c": "中节能哈密200MW风电功率预测项目",
        "projectProvince__c": "新疆维吾尔自治区",
        "bigCustShortName__c": "中节能",
        "serviceCycleStart__c": "2024-11-01",
        "serviceCycleEnd__c": "2026-10-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "冯主任",
        "initiator_dept": "运营部",
    },
    {
        "ticket_no": "SRV-2026-0007",
        "name": "三峡云南永胜光伏电站系统升级需求",
        "ownerId": "EMP000107",
        "dimDepart": "技术部",
        "caseSource": "7",  # 邮件
        "feedbackChannel__c": "7",  # 邮件
        "workOrderStatus__c": "4",  # 提级售后单
        "caseDescription": "永胜光伏电站现有功率预测系统版本较低（V3.2），无法支持多气象源融合预测。客户要求升级到最新版本V5.0，并增加超短期预测功能。",
        "caseStatus": "3",  # 处理中
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "4",  # 技术交流
        "problemType2__c": "10",  # 版本低需升级
        "problemType3__c": "15",  # 升级改造
        "problemResponsible__c": "王工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "陈主任",
        "feedbackUserContact__c": "13300133007",
        "feedbackCount__c": "2",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "升级方案已在内部评审通过，待客户确认实施时间",
        "planFeedbackTime__c": "2026-08-08",
        "requireSolveTime__c": "2026-08-30",
        "defectFlag__c": "1",
        "caseAccountId": "STN-YS-007",
        "custLevel1__c": "B",
        "projectName__c": "三峡永胜80MW光伏项目",
        "projectProvince__c": "云南省",
        "bigCustShortName__c": "三峡集团",
        "serviceCycleStart__c": "2025-01-15",
        "serviceCycleEnd__c": "2027-01-14",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "陈主任",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0008",
        "name": "龙源电力江苏如东海上风电通讯中断",
        "ownerId": "EMP000108",
        "dimDepart": "工程运维部",
        "caseSource": "1",  # 语音
        "feedbackChannel__c": "1",  # 400电话
        "workOrderStatus__c": "5",  # 大客户售后单
        "caseDescription": "如东海上风电场因台风影响导致通讯光缆中断，全场12台风机数据无法回传。需要紧急恢复通讯，并评估光缆加固方案。",
        "caseStatus": "3",  # 处理中
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "1",  # 现场问题
        "problemType2__c": "2",  # 硬件故障/更换
        "problemType3__c": "2",  # 通讯问题
        "problemResponsible__c": "马工",
        "problemDept__c": "工程运维部",
        "feedbackUserName__c": "蒋经理",
        "feedbackUserContact__c": "13200132008",
        "feedbackCount__c": "8",
        "needCallBack__c": "1",
        "isHandled__c": "1",
        "needOnSite__c": "1",
        "remark__c": "大客户，影响面积大，需要最高优先级处理。海洋天气好转后立即出海抢修。",
        "planFeedbackTime__c": "2026-07-30",
        "requireSolveTime__c": "2026-08-05",
        "defectFlag__c": "1",
        "caseAccountId": "STN-RD-008",
        "custLevel1__c": "A",
        "projectName__c": "龙源电力如东300MW海上风电项目",
        "projectProvince__c": "江苏省",
        "bigCustShortName__c": "龙源电力",
        "serviceCycleStart__c": "2024-06-01",
        "serviceCycleEnd__c": "2026-05-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "1",
        "initiator": "蒋经理",
        "initiator_dept": "运营部",
    },
    {
        "ticket_no": "SRV-2026-0009",
        "name": "中核集团福建福清核电站周边风场数据对接",
        "ownerId": "EMP000109",
        "dimDepart": "技术部",
        "caseSource": "8",  # APP
        "feedbackChannel__c": "8",  # 客户会议
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "福清核电站周边配套的30MW风电项目需要将功率预测数据接入核电站能量管理系统，需要开发数据接口并完成联调。",
        "caseStatus": "1",  # 待分配
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "4",  # 技术交流
        "problemType2__c": "12",  # 调度联调/并网
        "problemType3__c": "32",  # 调度联调
        "problemResponsible__c": "杨工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "黄主任",
        "feedbackUserContact__c": "13100131009",
        "feedbackCount__c": "1",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "接口协议为IEC 104，需要我方开发适配层",
        "planFeedbackTime__c": "2026-08-15",
        "requireSolveTime__c": "2026-09-15",
        "defectFlag__c": "1",
        "caseAccountId": "STN-FQ-009",
        "custLevel1__c": "A",
        "projectName__c": "中核福清30MW配套风电项目",
        "projectProvince__c": "福建省",
        "bigCustShortName__c": "中核集团",
        "serviceCycleStart__c": "2025-09-01",
        "serviceCycleEnd__c": "2027-08-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "黄主任",
        "initiator_dept": "技术部",
    },
    {
        "ticket_no": "SRV-2026-0010",
        "name": "华润广东湛江风电场年度精度报告需求",
        "ownerId": "EMP000110",
        "dimDepart": "数据中心",
        "caseSource": "99",  # 微信小程序
        "feedbackChannel__c": "10",  # 闭环回访
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "湛江风电场按合同约定需要提交年度功率预测精度报告，涵盖2025年7月至2026年6月的全部预测数据分析和KPI统计。",
        "caseStatus": "4",  # 待确认
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "3",  # 报告/回函
        "problemType2__c": "20",  # 服务报告
        "problemType3__c": "54",  # 年报
        "problemResponsible__c": "何工",
        "problemDept__c": "数据中心",
        "feedbackUserName__c": "钟站长",
        "feedbackUserContact__c": "13000130010",
        "feedbackCount__c": "1",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "客户需要纸质盖章版和电子版各一份",
        "planFeedbackTime__c": "2026-08-20",
        "requireSolveTime__c": "2026-09-10",
        "defectFlag__c": "1",
        "caseAccountId": "STN-ZJ-010",
        "custLevel1__c": "B",
        "projectName__c": "华润湛江150MW风电项目",
        "projectProvince__c": "广东省",
        "bigCustShortName__c": "华润集团",
        "serviceCycleStart__c": "2025-04-01",
        "serviceCycleEnd__c": "2027-03-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "钟站长",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0011",
        "name": "京能河北张家口风电场扩容功率预测适配",
        "ownerId": "EMP000111",
        "dimDepart": "技术部",
        "caseSource": "1",  # 语音
        "feedbackChannel__c": "1",  # 400电话
        "workOrderStatus__c": "6",  # 重要受理单
        "caseDescription": "张家口风电场二期扩容50MW，新增8台风机需要接入现有功率预测系统。需要重新配置预测模型并完成联调测试。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "5",  # 多部门处理
        "problemType2__c": "16",  # 扩容/减容
        "problemType3__c": "44",  # 扩容
        "problemResponsible__c": "林工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "高经理",
        "feedbackUserContact__c": "12900129011",
        "feedbackCount__c": "2",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "1",
        "remark__c": "扩容后总装机容量达到200MW，需要协调多个部门配合",
        "planFeedbackTime__c": "2026-08-12",
        "requireSolveTime__c": "2026-09-01",
        "defectFlag__c": "1",
        "caseAccountId": "STN-ZJK-011",
        "custLevel1__c": "A",
        "projectName__c": "京能张家口200MW风电项目",
        "projectProvince__c": "河北省",
        "bigCustShortName__c": "京能集团",
        "serviceCycleStart__c": "2024-08-01",
        "serviceCycleEnd__c": "2026-07-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "高经理",
        "initiator_dept": "运营部",
    },
    {
        "ticket_no": "SRV-2026-0012",
        "name": "国家能源集团山西大同光伏电站模型优化",
        "ownerId": "EMP000112",
        "dimDepart": "技术部",
        "caseSource": "2",  # 小组件
        "feedbackChannel__c": "12",  # 工程运维部
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "大同光伏电站的辐射传输模型在使用新气象源后出现预测偏差增大，需要调整模型参数以适应新气象源特性。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "2",  # 数据优化
        "problemType2__c": "14",  # 理论功率
        "problemType3__c": "68",  # 模型优化问题
        "problemResponsible__c": "周工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "徐主管",
        "feedbackUserContact__c": "12800128012",
        "feedbackCount__c": "1",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "气象源从ECMWF切换为GFS后出现的问题",
        "planFeedbackTime__c": "2026-08-07",
        "requireSolveTime__c": "2026-08-20",
        "defectFlag__c": "1",
        "caseAccountId": "STN-DT-012",
        "custLevel1__c": "B",
        "projectName__c": "国家能源集团大同120MW光伏项目",
        "projectProvince__c": "山西省",
        "bigCustShortName__c": "国家能源集团",
        "serviceCycleStart__c": "2025-05-01",
        "serviceCycleEnd__c": "2027-04-30",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "徐主管",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0013",
        "name": "中电建四川凉山风电场数据合格率考核",
        "ownerId": "EMP000113",
        "dimDepart": "数据中心",
        "caseSource": "3",  # 留言
        "feedbackChannel__c": "13",  # 数据中心
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "凉山风电场7月份数据合格率仅为78%，低于调度要求的90%标准。需要排查数据缺失原因并制定整改方案。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "2",  # 数据优化
        "problemType2__c": "1",  # 系统问题
        "problemType3__c": "22",  # 数据合格率考核
        "problemResponsible__c": "吴工",
        "problemDept__c": "数据中心",
        "feedbackUserName__c": "胡主管",
        "feedbackUserContact__c": "12700127013",
        "feedbackCount__c": "3",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "涉及调度考核处罚，客户非常着急",
        "planFeedbackTime__c": "2026-08-01",
        "requireSolveTime__c": "2026-08-10",
        "defectFlag__c": "1",
        "caseAccountId": "STN-LS-013",
        "custLevel1__c": "B",
        "projectName__c": "中电建凉山100MW风电项目",
        "projectProvince__c": "四川省",
        "bigCustShortName__c": "中电建",
        "serviceCycleStart__c": "2025-02-01",
        "serviceCycleEnd__c": "2027-01-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "胡主管",
        "initiator_dept": "运营部",
    },
    {
        "ticket_no": "SRV-2026-0014",
        "name": "粤电广东阳江海上风电数据补传",
        "ownerId": "EMP000114",
        "dimDepart": "数据中心",
        "caseSource": "4",  # 意见反馈
        "feedbackChannel__c": "14",  # 产品部
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "阳江海上风电场因海底光缆维修期间（7月20-25日）数据中断，现光缆已修复，需要补传缺失的6天历史数据。",
        "caseStatus": "3",  # 处理中
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "2",  # 数据优化
        "problemType2__c": "5",  # 数据采集
        "problemType3__c": "21",  # 数据补传
        "problemResponsible__c": "郑工",
        "problemDept__c": "数据中心",
        "feedbackUserName__c": "林运维",
        "feedbackUserContact__c": "12600126014",
        "feedbackCount__c": "1",
        "needCallBack__c": "2",
        "isHandled__c": "1",
        "needOnSite__c": "2",
        "remark__c": "本地历史数据完整，只需要远程导入",
        "planFeedbackTime__c": "2026-08-02",
        "requireSolveTime__c": "2026-08-05",
        "defectFlag__c": "1",
        "caseAccountId": "STN-YJ-014",
        "custLevel1__c": "A",
        "projectName__c": "粤电阳江400MW海上风电项目",
        "projectProvince__c": "广东省",
        "bigCustShortName__c": "粤电集团",
        "serviceCycleStart__c": "2024-10-01",
        "serviceCycleEnd__c": "2026-09-30",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "林运维",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0015",
        "name": "中广核湖北大悟风电场技术培训需求",
        "ownerId": "EMP000115",
        "dimDepart": "售后服务部",
        "caseSource": "5",  # 其他
        "feedbackChannel__c": "15",  # 售后服务部
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "大悟风电场新入职运维人员对功率预测系统操作不熟悉，需要安排一次现场培训，内容包括系统操作、日常维护和常见问题排查。",
        "caseStatus": "1",  # 待分配
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "4",  # 技术交流
        "problemType2__c": "29",  # 培训
        "problemType3__c": "73",  # 非入场 → 需要入场培训
        "problemResponsible__c": "王工",
        "problemDept__c": "售后服务部",
        "feedbackUserName__c": "何场长",
        "feedbackUserContact__c": "12500125015",
        "feedbackCount__c": "1",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "1",
        "remark__c": "希望安排有经验的培训讲师，时间可以协调",
        "planFeedbackTime__c": "2026-08-10",
        "requireSolveTime__c": "2026-08-31",
        "defectFlag__c": "1",
        "caseAccountId": "STN-DW-015",
        "custLevel1__c": "C",
        "projectName__c": "中广核大悟50MW风电项目",
        "projectProvince__c": "湖北省",
        "bigCustShortName__c": "中广核",
        "serviceCycleStart__c": "2025-08-01",
        "serviceCycleEnd__c": "2027-07-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "何场长",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0016",
        "name": "华能吉林白城风电场免考报告申请",
        "ownerId": "EMP000116",
        "dimDepart": "技术部",
        "caseSource": "6",  # 微信公众号
        "feedbackChannel__c": "17",  # 精度会议
        "workOrderStatus__c": "2",  # 投诉单
        "caseDescription": "白城风电场因2026年6月全场停电检修导致数据中断7天，向调度申请免考并需要我司出具免考支持报告。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "3",  # 报告/回函
        "problemType2__c": "19",  # 考核报告
        "problemType3__c": "49",  # 免考报告
        "problemResponsible__c": "张工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "秦站长",
        "feedbackUserContact__c": "12400124016",
        "feedbackCount__c": "2",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "调度免考申请截止日期为8月10日，时间紧迫",
        "planFeedbackTime__c": "2026-08-05",
        "requireSolveTime__c": "2026-08-10",
        "defectFlag__c": "1",
        "caseAccountId": "STN-BC-016",
        "custLevel1__c": "B",
        "projectName__c": "华能白城150MW风电项目",
        "projectProvince__c": "吉林省",
        "bigCustShortName__c": "华能集团",
        "serviceCycleStart__c": "2025-01-01",
        "serviceCycleEnd__c": "2026-12-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "秦站长",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0017",
        "name": "国电江西赣州光伏电站运维问题咨询",
        "ownerId": "EMP000117",
        "dimDepart": "售后服务部",
        "caseSource": "7",  # 邮件
        "feedbackChannel__c": "7",  # 邮件
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "赣州光伏电站运维人员在日常巡检中发现功率预测系统部分参数与现场实际情况不符，咨询如何调整参数配置。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "4",  # 技术交流
        "problemType2__c": "28",  # 电话咨询/答疑
        "problemType3__c": "5",  # 配置问题
        "problemResponsible__c": "李工",
        "problemDept__c": "售后服务部",
        "feedbackUserName__c": "方主管",
        "feedbackUserContact__c": "12300123017",
        "feedbackCount__c": "1",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "",
        "planFeedbackTime__c": "2026-08-03",
        "requireSolveTime__c": "2026-08-07",
        "defectFlag__c": "1",
        "caseAccountId": "STN-GZ-017",
        "custLevel1__c": "C",
        "projectName__c": "国电赣州30MW光伏项目",
        "projectProvince__c": "江西省",
        "bigCustShortName__c": "国电集团",
        "serviceCycleStart__c": "2025-10-01",
        "serviceCycleEnd__c": "2027-09-30",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "方主管",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0018",
        "name": "中节能甘肃酒泉风电场设备试验配合",
        "ownerId": "EMP000118",
        "dimDepart": "技术部",
        "caseSource": "8",  # APP
        "feedbackChannel__c": "18",  # 替换会议
        "workOrderStatus__c": "7",  # 非常重要受理单
        "caseDescription": "酒泉风电场即将进行电科院涉网试验，需要我司配合提供功率预测系统的实时数据接口和试验期间的数据保障。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "4",  # 技术交流
        "problemType2__c": "11",  # 试验
        "problemType3__c": "31",  # 电科院试验
        "problemResponsible__c": "赵工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "朱经理",
        "feedbackUserContact__c": "12200122018",
        "feedbackCount__c": "2",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "1",
        "remark__c": "试验时间为8月15日-20日，需要提前一周完成准备工作",
        "planFeedbackTime__c": "2026-08-08",
        "requireSolveTime__c": "2026-08-14",
        "defectFlag__c": "1",
        "caseAccountId": "STN-JQ-018",
        "custLevel1__c": "A",
        "projectName__c": "中节能酒泉200MW风电项目",
        "projectProvince__c": "甘肃省",
        "bigCustShortName__c": "中节能",
        "serviceCycleStart__c": "2024-12-01",
        "serviceCycleEnd__c": "2026-11-30",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "朱经理",
        "initiator_dept": "运营部",
    },
    {
        "ticket_no": "SRV-2026-0019",
        "name": "三峡西藏那曲风电场特殊环境设备问题",
        "ownerId": "EMP000119",
        "dimDepart": "工程运维部",
        "caseSource": "1",  # 语音
        "feedbackChannel__c": "1",  # 400电话
        "workOrderStatus__c": "3",  # A类售后单
        "caseDescription": "那曲风电场因高海拔（4500m+）和极端低温（-30°C）环境影响，数据采集设备频繁死机。需要更换适合高寒环境的工业级设备。",
        "caseStatus": "2",  # 待处理
        "problemLevel__c": "2",  # 重要紧急
        "problemType1__c": "1",  # 现场问题
        "problemType2__c": "2",  # 硬件故障/更换
        "problemType3__c": "8",  # 保期外
        "problemResponsible__c": "周工",
        "problemDept__c": "工程运维部",
        "feedbackUserName__c": "达瓦",
        "feedbackUserContact__c": "12100121019",
        "feedbackCount__c": "4",
        "needCallBack__c": "1",
        "isHandled__c": "2",
        "needOnSite__c": "1",
        "remark__c": "需要协调符合高海拔标准的工业级设备，并与客户协商费用",
        "planFeedbackTime__c": "2026-08-15",
        "requireSolveTime__c": "2026-09-01",
        "defectFlag__c": "1",
        "caseAccountId": "STN-NQ-019",
        "custLevel1__c": "B",
        "projectName__c": "三峡那曲50MW风电项目",
        "projectProvince__c": "西藏自治区",
        "bigCustShortName__c": "三峡集团",
        "serviceCycleStart__c": "2025-06-01",
        "serviceCycleEnd__c": "2027-05-31",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "达瓦",
        "initiator_dept": "运维部",
    },
    {
        "ticket_no": "SRV-2026-0020",
        "name": "粤电贵州毕节光伏电站消缺整改",
        "ownerId": "EMP000120",
        "dimDepart": "技术部",
        "caseSource": "2",  # 小组件
        "feedbackChannel__c": "11",  # 日常回访
        "workOrderStatus__c": "1",  # 售后单
        "caseDescription": "在日常回访中发现毕节光伏电站功率预测系统存在若干小缺陷，包括部分页面显示异常、报表导出功能偶尔失败等问题，需要进行消缺处理。",
        "caseStatus": "4",  # 待确认
        "problemLevel__c": "1",  # 常规问题
        "problemType1__c": "1",  # 现场问题
        "problemType2__c": "1",  # 系统问题
        "problemType3__c": "14",  # 消缺问题
        "problemResponsible__c": "孙工",
        "problemDept__c": "技术部",
        "feedbackUserName__c": "欧阳主管",
        "feedbackUserContact__c": "12000120020",
        "feedbackCount__c": "1",
        "needCallBack__c": "2",
        "isHandled__c": "2",
        "needOnSite__c": "2",
        "remark__c": "客户对系统整体功能满意，只希望修复这些小问题",
        "planFeedbackTime__c": "2026-08-12",
        "requireSolveTime__c": "2026-08-25",
        "defectFlag__c": "1",
        "caseAccountId": "STN-BJ-020",
        "custLevel1__c": "B",
        "projectName__c": "粤电毕节80MW光伏项目",
        "projectProvince__c": "贵州省",
        "bigCustShortName__c": "粤电集团",
        "serviceCycleStart__c": "2025-03-01",
        "serviceCycleEnd__c": "2027-02-28",
        "isOfflineApply__c": "2",
        "isOverdueService__c": "2",
        "initiator": "欧阳主管",
        "initiator_dept": "运维部",
    },
]

# ── SQL 语句 ──────────────────────────────────────────

CLEANUP_STATEMENTS = [
    "DROP VIEW IF EXISTS ticket_view CASCADE",
    "DROP TABLE IF EXISTS ticket CASCADE",
    "DROP TABLE IF EXISTS source_message CASCADE",
    "DROP TABLE IF EXISTS wechat_user CASCADE",
    "DROP TABLE IF EXISTS project_info CASCADE",
    "DELETE FROM bad_case_sample",
    "DELETE FROM workorder_audit_log",
    "DELETE FROM workorder_stash",
    "DELETE FROM workorder_review",
]

CREATE_TICKET_SOURCE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS wechat_user (
        user_id BIGINT PRIMARY KEY,
        nick_name VARCHAR(64) NOT NULL,
        source VARCHAR(64) NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_message (
        id BIGINT PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES wechat_user(user_id),
        source VARCHAR(64) NOT NULL,
        content TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ticket (
        id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
        ticket_no VARCHAR(100) NOT NULL UNIQUE,
        source_id BIGINT REFERENCES source_message(id),
        "ownerId" VARCHAR(64),
        "dimDepart" VARCHAR(128),
        "entityType" VARCHAR(32) DEFAULT '11010045500001',
        name VARCHAR(255),
        "caseSource" VARCHAR(32),
        "feedbackChannel__c" VARCHAR(32),
        "workOrderStatus__c" VARCHAR(32),
        "caseDescription" TEXT,
        "caseStatus" VARCHAR(16),
        "caseAccountId" VARCHAR(64),
        "custLevel1__c" VARCHAR(32),
        "projectName__c" VARCHAR(255),
        "projectProvince__c" VARCHAR(64),
        "bigCustShortName__c" VARCHAR(128),
        "serviceCycleStart__c" VARCHAR(32),
        "serviceCycleEnd__c" VARCHAR(32),
        "isOfflineApply__c" VARCHAR(4),
        "isOverdueService__c" VARCHAR(4),
        "problemLevel__c" VARCHAR(32),
        "problemType1__c" VARCHAR(32),
        "problemType2__c" VARCHAR(64),
        "problemType3__c" VARCHAR(64),
        "feedbackCount__c" VARCHAR(16),
        "problemResponsible__c" VARCHAR(64),
        "problemDept__c" VARCHAR(128),
        "feedbackUserName__c" VARCHAR(64),
        "feedbackUserContact__c" VARCHAR(16),
        "needCallBack__c" VARCHAR(4),
        "isHandled__c" VARCHAR(4),
        "needOnSite__c" VARCHAR(4),
        "remark__c" TEXT,
        "relatedAttachment__c" VARCHAR(255),
        "planFeedbackTime__c" VARCHAR(32),
        "requireSolveTime__c" VARCHAR(32),
        "defectFlag__c" VARCHAR(4) DEFAULT '1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_info (
        "caseAccountId" VARCHAR(64) PRIMARY KEY,
        "custLevel1__c" VARCHAR(32),
        "projectName__c" VARCHAR(255),
        "projectProvince__c" VARCHAR(64),
        "bigCustShortName__c" VARCHAR(128),
        "serviceCycleStart__c" VARCHAR(32),
        "serviceCycleEnd__c" VARCHAR(32),
        "isOfflineApply__c" VARCHAR(4),
        "isOverdueService__c" VARCHAR(4)
    )
    """,
]

DROP_TICKET_VIEW = "DROP VIEW IF EXISTS ticket_view CASCADE"

CREATE_TICKET_VIEW = """
CREATE VIEW ticket_view AS
SELECT
    t.id,
    t.ticket_no,
    t."ownerId",
    t."dimDepart",
    t."entityType",
    t.name,
    t."caseSource",
    t."feedbackChannel__c",
    t."workOrderStatus__c",
    t."caseDescription",
    t."caseStatus",
    t."problemLevel__c",
    t."problemType1__c",
    t."problemType2__c",
    t."problemType3__c",
    t."feedbackCount__c",
    t."problemResponsible__c",
    t."problemDept__c",
    t."feedbackUserName__c",
    t."feedbackUserContact__c",
    t."needCallBack__c",
    t."isHandled__c",
    t."needOnSite__c",
    t."remark__c",
    t."relatedAttachment__c",
    t."planFeedbackTime__c",
    t."requireSolveTime__c",
    t."defectFlag__c",
    pi."caseAccountId",
    pi."custLevel1__c",
    pi."projectName__c",
    pi."projectProvince__c",
    pi."bigCustShortName__c",
    pi."serviceCycleStart__c",
    pi."serviceCycleEnd__c",
    pi."isOfflineApply__c",
    pi."isOverdueService__c"
FROM ticket t
LEFT JOIN project_info pi ON t."caseAccountId" = pi."caseAccountId"
"""


async def seed(engine) -> None:
    """主种子函数。"""
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        # ── 0. 清理旧数据 ──
        print("🧹 清理旧表和视图...")
        for stmt in CLEANUP_STATEMENTS:
            await db.execute(text(stmt))

        # ── 1. 创建源数据表（public）──
        print("📦 创建源数据表（public）...")
        for i, stmt in enumerate(CREATE_TICKET_SOURCE_TABLES):
            print(f"  → 创建表 {i+1}/{len(CREATE_TICKET_SOURCE_TABLES)}")
            await db.execute(text(stmt))

        # ── 2. 创建 ticket_view 视图 ──
        print("👁  创建 ticket_view 视图...")
        await db.execute(text(DROP_TICKET_VIEW))
        await db.execute(text(CREATE_TICKET_VIEW))

        # ── 3. 插入种子数据 ──
        print(f"🌱 插入 {len(TICKETS)} 条工单数据...")

        # 3a. 插入 wechat_user（每个工单的发起人）
        user_counter = 1000
        for t in TICKETS:
            user_counter += 1
            await db.execute(
                text("""
                    INSERT INTO wechat_user (user_id, nick_name, source)
                    VALUES (:uid, :nick, :source)
                    ON CONFLICT (user_id) DO NOTHING
                """),
                {"uid": user_counter, "nick": t["initiator"], "source": t["initiator_dept"]},
            )

        # 3b. 插入 source_message
        msg_counter = 2000
        for i, t in enumerate(TICKETS):
            msg_counter += 1
            uid = 1001 + i
            await db.execute(
                text("""
                    INSERT INTO source_message (id, user_id, source, content)
                    VALUES (:id, :uid, :source, :content)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": msg_counter,
                    "uid": uid,
                    "source": t["feedbackChannel__c"],
                    "content": t["caseDescription"][:200],
                },
            )

        # 3c. 插入 project_info
        seen_projects = set()
        for t in TICKETS:
            aid = t["caseAccountId"]
            if aid in seen_projects:
                continue
            seen_projects.add(aid)
            await db.execute(
                text("""
                    INSERT INTO project_info (
                        "caseAccountId", "custLevel1__c", "projectName__c",
                        "projectProvince__c", "bigCustShortName__c",
                        "serviceCycleStart__c", "serviceCycleEnd__c",
                        "isOfflineApply__c", "isOverdueService__c"
                    ) VALUES (
                        :aid, :cl, :pn, :pp, :bc,
                        :scs, :sce, :ioa, :ios
                    )
                    ON CONFLICT ("caseAccountId") DO NOTHING
                """),
                {
                    "aid": aid,
                    "cl": t["custLevel1__c"],
                    "pn": t["projectName__c"],
                    "pp": t["projectProvince__c"],
                    "bc": t["bigCustShortName__c"],
                    "scs": t["serviceCycleStart__c"],
                    "sce": t["serviceCycleEnd__c"],
                    "ioa": t["isOfflineApply__c"],
                    "ios": t["isOverdueService__c"],
                },
            )

        # 3d. 插入 ticket
        msg_counter = 2000
        for i, t in enumerate(TICKETS):
            msg_counter += 1
            await db.execute(
                text("""
                    INSERT INTO ticket (
                        ticket_no, source_id,
                        "ownerId", "dimDepart", "entityType", name,
                        "caseSource", "feedbackChannel__c", "workOrderStatus__c",
                        "caseDescription", "caseStatus",
                        "problemLevel__c", "problemType1__c", "problemType2__c", "problemType3__c",
                        "problemResponsible__c", "problemDept__c",
                        "feedbackUserName__c", "feedbackUserContact__c",
                        "feedbackCount__c", "needCallBack__c", "isHandled__c", "needOnSite__c",
                        "remark__c", "planFeedbackTime__c", "requireSolveTime__c", "defectFlag__c",
                        "caseAccountId"
                    ) VALUES (
                        :ticket_no, :source_id,
                        :ownerId, :dimDepart, :entityType, :name,
                        :caseSource, :feedbackChannel__c, :workOrderStatus__c,
                        :caseDescription, :caseStatus,
                        :problemLevel__c, :problemType1__c, :problemType2__c, :problemType3__c,
                        :problemResponsible__c, :problemDept__c,
                        :feedbackUserName__c, :feedbackUserContact__c,
                        :feedbackCount__c, :needCallBack__c, :isHandled__c, :needOnSite__c,
                        :remark__c, :planFeedbackTime__c, :requireSolveTime__c, :defectFlag__c,
                        :caseAccountId
                    )
                    ON CONFLICT (ticket_no) DO NOTHING
                """),
                {
                    "ticket_no": t["ticket_no"],
                    "source_id": msg_counter,
                    "ownerId": t.get("ownerId", ""),
                    "dimDepart": t.get("dimDepart", ""),
                    "entityType": "11010045500001",
                    "name": t["name"],
                    "caseSource": t["caseSource"],
                    "feedbackChannel__c": t["feedbackChannel__c"],
                    "workOrderStatus__c": t["workOrderStatus__c"],
                    "caseDescription": t["caseDescription"],
                    "caseStatus": t["caseStatus"],
                    "problemLevel__c": t["problemLevel__c"],
                    "problemType1__c": t["problemType1__c"],
                    "problemType2__c": t["problemType2__c"],
                    "problemType3__c": t["problemType3__c"],
                    "problemResponsible__c": t["problemResponsible__c"],
                    "problemDept__c": t["problemDept__c"],
                    "feedbackUserName__c": t["feedbackUserName__c"],
                    "feedbackUserContact__c": t["feedbackUserContact__c"],
                    "feedbackCount__c": t["feedbackCount__c"],
                    "needCallBack__c": t["needCallBack__c"],
                    "isHandled__c": t["isHandled__c"],
                    "needOnSite__c": t["needOnSite__c"],
                    "remark__c": t["remark__c"],
                    "planFeedbackTime__c": t["planFeedbackTime__c"],
                    "requireSolveTime__c": t["requireSolveTime__c"],
                    "defectFlag__c": t["defectFlag__c"],
                    "caseAccountId": t["caseAccountId"],
                },
            )

        await db.commit()
        print("  ✅ 源数据插入完成")

        # ── 4. 幂等导入到 workorder_review ──
        print("📥 导入到 workorder_review...")
        from app.services.import_service import import_workorders
        count = await import_workorders(db)
        print(f"  ✅ 导入 {count} 条记录")

        # ── 5. 设置不同的审核状态 ──
        print("🎨 设置多样化的审核状态...")
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 获取所有 workorder_review 记录
        result = await db.execute(
            text("SELECT id, ticket_no FROM workorder_review ORDER BY ticket_no")
        )
        all_rows = list(result.mappings())
        ticket_to_wid = {r["ticket_no"]: r["id"] for r in all_rows}

        # 分组设置状态
        all_tickets = sorted(ticket_to_wid.keys())

        # Group 1: confirmed (已审核通过) — 5条: 0001 ~ 0005
        confirmed_nos = all_tickets[:5]
        for i, tno in enumerate(confirmed_nos):
            wid = ticket_to_wid[tno]
            reviewer = REVIEWERS[i % len(REVIEWERS)]
            reviewed_at = now - timedelta(days=i + 1, hours=i * 3)
            duration = 120 + i * 60  # 2min ~ 6min
            started_at = reviewed_at - timedelta(seconds=duration)
            await db.execute(
                text("""
                    UPDATE workorder_review
                    SET review_status = 'confirmed',
                        reviewed_at = :reviewed_at,
                        reviewed_by = :reviewed_by,
                        review_started_at = :started_at,
                        review_duration_seconds = :duration,
                        review_notes = :notes
                    WHERE id = :id
                """),
                {
                    "id": wid,
                    "reviewed_at": reviewed_at,
                    "reviewed_by": reviewer["name"],
                    "started_at": started_at,
                    "duration": duration,
                    "notes": f"已审核通过，变更记录已同步。审核人备注：确认AI填充结果准确无误。" if i == 0 else f"第{i+1}次审核通过",
                },
            )

        # Group 2: pending_review + reject_history (被驳回过) — 3条: 0006 ~ 0008
        rejected_nos = all_tickets[5:8]
        for i, tno in enumerate(rejected_nos):
            wid = ticket_to_wid[tno]
            reviewer = REVIEWERS[i % len(REVIEWERS)]
            reject_count = i + 1
            rejected_at = now - timedelta(days=1, hours=i * 4)
            await db.execute(
                text("""
                    UPDATE workorder_review
                    SET review_status = 'pending_review',
                        reject_count = :reject_count,
                        last_reject_reason = :reason,
                        last_rejected_by = :reviewed_by,
                        last_rejected_at = :rejected_at,
                        review_duration_seconds = :duration
                    WHERE id = :id
                """),
                {
                    "id": wid,
                    "reject_count": reject_count,
                    "reason": [
                        "AI填充的问题分类不准确，请人工修正后重新提交",
                        "反馈人联系方式缺失，请补充完整信息",
                        "工单描述不够详细，需要补充具体的故障现象和影响范围",
                    ][i],
                    "reviewed_by": reviewer["name"],
                    "rejected_at": rejected_at,
                    "duration": 90 + i * 45,
                },
            )

        # Group 3: stashed (审核暂存) — 1条: 0009
        stashed_no = all_tickets[8]
        wid_9 = ticket_to_wid[stashed_no]
        stash_started = now - timedelta(hours=2)
        await db.execute(
            text("""
                UPDATE workorder_review
                SET review_status = 'stashed',
                    review_started_at = :started_at
                WHERE id = :id
            """),
            {"id": wid_9, "started_at": stash_started},
        )

        # 为暂存工单添加 stash 数据
        await db.execute(
            text("DELETE FROM workorder_stash WHERE workorder_id = :wid"),
            {"wid": wid_9},
        )
        await db.execute(
            text("""
                INSERT INTO workorder_stash (workorder_id, field_states, notes)
                VALUES (:wid, CAST(:states AS jsonb), :notes)
            """),
            {
                "wid": wid_9,
                "states": '{"caseDescription": {"status": "edited", "currentValue": "敦煌光伏电站三区逆变器数据从7月25日起停止上传，经现场排查发现采集终端通讯模块故障，需更换通讯模块并重新配置IP地址。"}, "problemLevel__c": {"status": "confirmed", "currentValue": "2"}}',
                "notes": "正在核实通讯模块型号，暂时保存进度",
            },
        )

        # Group 4: confirmed + sync_failed (已通过但同步失败) — 2条: 0010 ~ 0011
        sync_failed_nos = all_tickets[9:11]
        for i, tno in enumerate(sync_failed_nos):
            wid = ticket_to_wid[tno]
            reviewer = REVIEWERS[(i + 1) % len(REVIEWERS)]
            reviewed_at = now - timedelta(days=2, hours=i * 6)
            duration = 150 + i * 30
            started_at = reviewed_at - timedelta(seconds=duration)
            await db.execute(
                text("""
                    UPDATE workorder_review
                    SET review_status = 'confirmed',
                        reviewed_at = :reviewed_at,
                        reviewed_by = :reviewed_by,
                        review_started_at = :started_at,
                        review_duration_seconds = :duration,
                        sync_status = 'failed',
                        sync_attempts = :attempts,
                        sync_last_error = :error,
                        review_notes = :notes
                    WHERE id = :id
                """),
                {
                    "id": wid,
                    "reviewed_at": reviewed_at,
                    "reviewed_by": reviewer["name"],
                    "started_at": started_at,
                    "duration": duration,
                    "attempts": 3,
                    "error": [
                        "销售易 API 超时: Connection to api.xiaoshouyi.com timed out after 5.0s (3 retries exhausted)",
                        "销售易 API 返回 500: Internal Server Error — upstream service unavailable",
                    ][i],
                    "notes": "已通过审核，销售易同步失败需手动重试",
                },
            )

        # Group 5: confirmed + synced (已通过已同步) — 1条: 0012
        synced_no = all_tickets[11]
        wid_12 = ticket_to_wid[synced_no]
        synced_reviewer = REVIEWERS[2]
        synced_reviewed = now - timedelta(days=3)
        synced_duration = 200
        synced_started = synced_reviewed - timedelta(seconds=synced_duration)
        await db.execute(
            text("""
                UPDATE workorder_review
                SET review_status = 'confirmed',
                    reviewed_at = :reviewed_at,
                    reviewed_by = :reviewed_by,
                    review_started_at = :started_at,
                    review_duration_seconds = :duration,
                    sync_status = 'synced',
                    sync_attempts = 1,
                    sync_external_id = :ext_id,
                    sync_idempotency_key = :key,
                    sync_started_at = :sync_started,
                    review_notes = :notes
                WHERE id = :id
            """),
            {
                "id": wid_12,
                "reviewed_at": synced_reviewed,
                "reviewed_by": synced_reviewer["name"],
                "started_at": synced_started,
                "duration": synced_duration,
                "ext_id": "XSY-EXT-20260726001",
                "key": f"confirm-{synced_no}-{uuid.uuid4().hex[:8]}",
                "sync_started": synced_reviewed + timedelta(seconds=1),
                "notes": "审核通过并成功同步至销售易",
            },
        )

        # Group 6: 剩余的保持 pending_review — 0013 ~ 0020
        # (default status, no changes needed)

        await db.commit()
        print("  ✅ 审核状态设置完成")

        # ── 6. 为已确认的工单生成审核日志 ──
        print("📝 生成审核日志...")
        log_entries = []

        # 为 confirmed 工单生成日志
        for i, tno in enumerate(confirmed_nos):
            wid = ticket_to_wid[tno]
            reviewer = REVIEWERS[i % len(REVIEWERS)]
            session_id = f"sess-confirm-{wid}"
            now_time = now - timedelta(days=i + 1)
            changes = [
                ("/caseDescription", "工单描述", None, TICKETS[i]["caseDescription"], "replace"),
                ("/problemLevel__c", "问题等级", None, TICKETS[i]["problemLevel__c"], "replace"),
                ("/problemResponsible__c", "问题责任人", None, TICKETS[i]["problemResponsible__c"], "replace"),
            ]
            for path, label, old, new, ctype in changes:
                log_entries.append({
                    "workorder_id": wid,
                    "session_id": session_id,
                    "field_path": path,
                    "field_label": label,
                    "old_value": old,
                    "new_value": new,
                    "change_type": ctype,
                    "operator_id": reviewer["id"],
                    "operator_name": reviewer["name"],
                    "operated_at": now_time,
                })

        # 为 rejected 工单生成驳回日志
        for i, tno in enumerate(rejected_nos):
            wid = ticket_to_wid[tno]
            reviewer = REVIEWERS[i % len(REVIEWERS)]
            session_id = f"sess-reject-{wid}"
            rejected_at = now - timedelta(days=1, hours=i * 4)
            log_entries.append({
                "workorder_id": wid,
                "session_id": session_id,
                "field_path": "/review_status",
                "field_label": "审核状态",
                "old_value": "reviewing",
                "new_value": "rejected",
                "change_type": "replace",
                "operator_id": reviewer["id"],
                "operator_name": reviewer["name"],
                "operated_at": rejected_at,
            })

        for entry in log_entries:
            await db.execute(
                text("""
                    INSERT INTO workorder_audit_log
                        (workorder_id, session_id, field_path, field_label,
                         old_value, new_value, change_type, operator_id,
                         operator_name, operated_at)
                    VALUES
                        (:workorder_id, :session_id, :field_path, :field_label,
                         :old_value, :new_value, :change_type, :operator_id,
                         :operator_name, :operated_at)
                """),
                entry,
            )

        await db.commit()
        print(f"  ✅ 生成 {len(log_entries)} 条审核日志")

        # ── 7. 生成 bad_case 样本 ──
        print("🔖 生成 bad_case 样本...")
        # 获取已生成的 audit logs
        result = await db.execute(
            text("""
                SELECT id, workorder_id, field_path, old_value, new_value
                FROM workorder_audit_log
                WHERE field_path != '/review_status'
                ORDER BY id
                LIMIT 10
            """)
        )
        audit_rows = list(result.mappings())

        bad_case_count = 0
        for row in audit_rows:
            await db.execute(
                text("""
                    INSERT INTO bad_case_sample
                        (workorder_id, audit_log_id, field_path,
                         ai_value, human_value, sample_status, source)
                    VALUES
                        (:wid, :alid, :fp, :av, :hv, 'pending', 'review_correction')
                    ON CONFLICT DO NOTHING
                """),
                {
                    "wid": row["workorder_id"],
                    "alid": row["id"],
                    "fp": row["field_path"],
                    "av": row["old_value"],
                    "hv": row["new_value"],
                },
            )
            bad_case_count += 1

        await db.commit()
        print(f"  ✅ 生成 {bad_case_count} 条 bad_case 样本")

    # ── 8. 打印汇总 ──
    print("\n" + "=" * 60)
    print("🎉 测试数据种子完成！")
    print("=" * 60)

    async with async_session() as db:
        result = await db.execute(
            text("""
                SELECT review_status, COUNT(*) as cnt
                FROM workorder_review
                GROUP BY review_status
                ORDER BY review_status
            """)
        )
        print("\n📊 工单状态分布：")
        for row in result.mappings():
            status_map = {
                "pending_review": "⏳ 待审核",
                "reviewing": "🔍 审核中",
                "confirmed": "✅ 已通过",
                "stashed": "📦 已暂存",
                "returned": "↩️  已退回",
            }
            label = status_map.get(row["review_status"], row["review_status"])
            print(f"  {label}: {row['cnt']} 条")

        # Sync status stats
        result = await db.execute(
            text("""
                SELECT sync_status, COUNT(*) as cnt
                FROM workorder_review
                GROUP BY sync_status
                ORDER BY sync_status
            """)
        )
        print("\n🔄 同步状态分布：")
        for row in result.mappings():
            print(f"  {row['sync_status']}: {row['cnt']} 条")

        # Count audit logs
        result = await db.execute(text("SELECT COUNT(*) as cnt FROM workorder_audit_log"))
        print(f"\n📝 审核日志: {result.scalar()} 条")

        # Count bad cases
        result = await db.execute(text("SELECT COUNT(*) as cnt FROM bad_case_sample"))
        print(f"🔖 坏例样本: {result.scalar()} 条")

        # Count stashes
        result = await db.execute(text("SELECT COUNT(*) as cnt FROM workorder_stash"))
        print(f"💾 暂存记录: {result.scalar()} 条")

    print("\n✅ 可以启动后端服务并使用以下接口测试：")
    print("  GET  /api/workorders                    — 工单列表")
    print("  GET  /api/workorders/{id}               — 工单详情")
    print("  POST /api/workorders/{id}/confirm       — 审核确认")
    print("  GET  /api/workorders/{id}/audit-logs    — 审核日志")
    print("  POST /api/workorders/{id}/stash         — 暂存进度")
    print("  GET  /api/admin/sync-failures           — 同步失败列表")
    print("  POST /api/admin/sync-failures/{id}/retry — 重试同步")
    print("  GET  /api/stats/overview                — 统计概览")


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        await seed(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
