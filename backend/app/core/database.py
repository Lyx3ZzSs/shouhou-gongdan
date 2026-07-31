from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """获取数据库会话。调用方负责事务管理（db.begin() / db.commit() / db.rollback()）。
    异常时自动回滚未提交事务，避免连接池泄漏。"""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine():
    """关闭数据库连接池（用于应用优雅关闭）。"""
    await engine.dispose()
