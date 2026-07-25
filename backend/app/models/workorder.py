from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship

from .base import Base


class WorkOrder(Base):
    __tablename__ = "workorder"

    # NOTE: 此模型仅包含审核功能所需字段（约52列）。
    # 业务字段来自销售易 serviceCase API（POST /openapi/insertServiceCase）。
    # 生产环境迁移请务必使用手动编写的迁移脚本，而非 autogenerate。

    # Primary key
    id = Column(String(64), primary_key=True)

    # Review / audit tracking
    version = Column(Integer, default=1, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(64), nullable=True)
    reject_count = Column(Integer, default=0, nullable=False)
    last_reject_reason = Column(Text, nullable=True)
    last_rejected_by = Column(String(64), nullable=True)
    last_rejected_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    sync_status = Column(String(16), nullable=False, default='pending')
    # 'pending' | 'syncing' | 'synced' | 'failed' — 销售易同步状态
    sync_attempts = Column(Integer, nullable=False, default=0)
    sync_last_error = Column(Text, nullable=True)
    sync_idempotency_key = Column(String(128), nullable=True)
    # 去重键：同一次确认提交的多次同步尝试共享同一 key，防止重复创建
    sync_external_id = Column(String(64), nullable=True)
    # 销售易返回的工单 ID，非空时表示已在销售易创建成功（幂等检查点）
    sync_started_at = Column(DateTime(timezone=True), nullable=True)
    # 同步开始时间，用于判断 syncing 状态是否超时（recover_orphan_syncs）

    # Review timing
    review_started_at = Column(DateTime(timezone=True), nullable=True)
    # 审核开始时间（锁首次获取时记录）
    review_duration_seconds = Column(Integer, nullable=True)
    # 审核耗时（秒），确认/驳回时计算

    # Read-only metadata
    serial_number = Column(String(64), nullable=True)
    status = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=True)
    initiator = Column(String(64), nullable=True)
    initiator_department = Column(String(128), nullable=True)

    # ---- 销售易 serviceCase API 业务字段 (33 + 1 hidden) ----

    # Required fields (not_null=1 in API spec)
    ownerId = Column(String(64), nullable=True)                # 所有人（北森员工编码）
    dimDepart = Column(String(128), nullable=True)              # 所属部门（北森部门编码）
    entityType = Column(String(32), nullable=True, default='11010045500001')  # 业务类型
    name = Column(String(255), nullable=True)                   # 工单主题
    caseSource = Column(String(32), nullable=True)              # 工单来源
    feedbackChannel__c = Column(String(32), nullable=True)      # 反馈渠道
    workOrderStatus__c = Column(String(32), nullable=True)      # 工单类型
    caseDescription = Column(Text, nullable=True)               # 工单描述
    caseStatus = Column(String(16), nullable=True)              # 工单状态

    # Optional fields
    caseAccountId = Column(String(64), nullable=True)           # 场站名称（场站编号）
    custLevel1__c = Column(String(32), nullable=True)           # 客户级别
    projectName__c = Column(String(255), nullable=True)         # 项目名称（项目编号）
    projectProvince__c = Column(String(64), nullable=True)      # 项目省份
    bigCustShortName__c = Column(String(128), nullable=True)    # 大客户简称
    serviceCycleStart__c = Column(String(32), nullable=True)    # 周期服务开始时间（时间戳）
    serviceCycleEnd__c = Column(String(32), nullable=True)      # 周期服务结束时间（时间戳）
    isOfflineApply__c = Column(String(4), nullable=True)        # 是否线下申请
    isOverdueService__c = Column(String(4), nullable=True)      # 是否超期服务
    problemLevel__c = Column(String(32), nullable=True)         # 问题等级
    problemType1__c = Column(String(32), nullable=True)         # 问题分类-1级
    problemType2__c = Column(String(64), nullable=True)         # 问题分类-2级
    problemType3__c = Column(String(64), nullable=True)         # 问题分类-3级
    feedbackCount__c = Column(String(16), nullable=True)        # 反馈次数
    problemResponsible__c = Column(String(64), nullable=True)   # 问题责任人（北森员工编码）
    problemDept__c = Column(String(128), nullable=True)         # 问题责任部门（北森部门编码）
    feedbackUserName__c = Column(String(64), nullable=True)     # 反馈人姓名
    feedbackUserContact__c = Column(String(16), nullable=True)  # 反馈人联系方式（11位手机号）
    needCallBack__c = Column(String(4), nullable=True)          # 是否要求回电话
    isHandled__c = Column(String(4), nullable=True)             # 是否处理
    needOnSite__c = Column(String(4), nullable=True)            # 是否要求进场
    remark__c = Column(Text, nullable=True)                     # 备注
    relatedAttachment__c = Column(String(255), nullable=True)  # 相关附件
    planFeedbackTime__c = Column(String(32), nullable=True)     # 方案反馈时间（时间戳）
    requireSolveTime__c = Column(String(32), nullable=True)     # 要求解决时间（时间戳）

    # Hidden field — sent to API but not displayed in UI
    defectFlag__c = Column(String(4), nullable=True, default='1')  # 缺陷标记

    # ORM relationships (lazy='raise'：访问时若未显式 eager-load 则抛出异常，避免意外 N+1）。
    # 仅定义正向关系（WorkOrder → 关联表），不设 back_populates 以避免循环导入问题。
    audit_logs = relationship(
        "WorkOrderAuditLog", lazy="raise",
        primaryjoin="WorkOrder.id == foreign(WorkOrderAuditLog.workorder_id)",
    )
    stash = relationship(
        "WorkOrderStash", lazy="raise", uselist=False,
        primaryjoin="WorkOrder.id == foreign(WorkOrderStash.workorder_id)",
    )
