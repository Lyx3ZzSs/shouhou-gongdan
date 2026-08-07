"""v_ticket 视图模型 — 只读，映射 ticket_source.ticket LEFT JOIN project_info。"""

from sqlalchemy import Column, String, BigInteger, Text
from .base import Base


class VTicket(Base):
    """v_ticket 视图 — 工单业务数据的统一查询入口（只读）。"""

    __tablename__ = "v_ticket"

    # ticket 标识
    id = Column(BigInteger, primary_key=True)
    ticket_no = Column(String(100))

    # 销售易业务字段（驼峰/__c 命名，与前端约定一致）
    ownerId = Column(String(64))
    dimDepart = Column(String(64))
    entityType = Column(String(64))
    name = Column(String(100))
    caseSource = Column(String(20))
    feedbackChannel__c = Column(String(20))
    workOrderStatus__c = Column(String(50))
    caseDescription = Column(Text)
    caseStatus = Column(String(20))
    problemLevel__c = Column(String(32))
    feedbackUserContact__c = Column(String(200))
    feedbackUserName__c = Column(String(200))
    problemResponsible__c = Column(String(100))
    problemDept__c = Column(String(100))
    problemType1__c = Column(String(100))
    problemType2__c = Column(String(100))
    problemType3__c = Column(String(100))
    feedbackCount__c = Column(String(100))
    needCallBack__c = Column(String(20))
    isHandled__c = Column(String(20))
    needOnSite__c = Column(String(20))
    remark__c = Column(Text)
    relatedAttachment__c = Column(String(512))
    planFeedbackTime__c = Column(String(100))
    requireSolveTime__c = Column(String(100))
    defectFlag__c = Column(String(20))

    # project_info 字段（来自 LEFT JOIN）
    caseAccountId = Column(String(100))
    custLevel1__c = Column(String(100))
    projectName__c = Column(String(200))
    projectProvince__c = Column(String(100))
    bigCustShortName__c = Column(String(200))
    serviceCycleStart__c = Column(String)
    serviceCycleEnd__c = Column(String)
    isOfflineApply__c = Column(String(4))
    isOverdueService__c = Column(String)

    def to_dict(self) -> dict:
        """将视图行转为 dict，方便 merge 操作。"""
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
        }
