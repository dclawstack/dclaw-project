from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.core.config import settings
from app.models.base import Base


def _build_engine():
    if settings.is_sqlite:
        # SQLite doesn't support PG-style pooling args; use NullPool semantics
        # by skipping pool_pre_ping (no remote socket to ping).
        return create_async_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return create_async_engine(
        settings.database_url,
        echo=settings.app_env == "dev",
        pool_pre_ping=True,
    )


engine = _build_engine()


async def get_db() -> AsyncSession:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    # Importing all models so their tables are registered on Base.metadata
    # before create_all runs (critical for SQLite dev mode + first boot).
    from app.models import (  # noqa: F401
        user,
        workspace,
        project,
        task,
        milestone,
        tag,
        comment,
        task_dependency,
        time_entry,
        notification,
        agent_run,
        embedding,
        document,
        sprint,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
