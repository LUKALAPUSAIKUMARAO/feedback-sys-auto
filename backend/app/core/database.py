from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from app.core.config import settings
import structlog

log = structlog.get_logger()

_sqlite = settings.DATABASE_URL.startswith("sqlite")

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    **({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool} if _sqlite else
       {"pool_size": 20, "max_overflow": 0, "pool_pre_ping": True}),
)

sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=settings.DEBUG,
    **({"connect_args": {"check_same_thread": False}} if _sqlite else
       {"pool_size": 10, "max_overflow": 0, "pool_pre_ping": True}),
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("database.tables_created")
