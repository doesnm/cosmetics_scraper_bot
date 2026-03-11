from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_tables() -> None:
    import src.models  # noqa: F401 — register ORM models with Base.metadata

    from .base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
