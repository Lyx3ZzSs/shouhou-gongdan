"""审核统计 API — 总览、按人、趋势、耗时分布、状态分布。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def stats_overview(db: AsyncSession = Depends(get_db)):
    """总览：已审核总数、今日审核、平均耗时、通过率、待审核数。"""
    svc = StatsService(db)
    return await svc.get_overview()


@router.get("/by-reviewer")
async def stats_by_reviewer(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    """按审核人员统计审核量、通过/驳回数、平均耗时。"""
    svc = StatsService(db)
    return await svc.get_by_reviewer(from_date, to_date)


@router.get("/trends")
async def stats_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """每日审核趋势（最近 N 天）。"""
    svc = StatsService(db)
    return await svc.get_trends(days)


@router.get("/duration-distribution")
async def stats_duration_distribution(db: AsyncSession = Depends(get_db)):
    """审核耗时分布（按区间）。"""
    svc = StatsService(db)
    return await svc.get_duration_distribution()


@router.get("/status-distribution")
async def stats_status_distribution(db: AsyncSession = Depends(get_db)):
    """工单状态分布（待审核/已通过/已驳回）。"""
    svc = StatsService(db)
    return await svc.get_status_distribution()
