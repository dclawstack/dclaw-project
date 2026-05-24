import os
import asyncio
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from app.api.main import app
from app.core.database import get_db
from app.models.base import Base
# Ensure all models are registered on Base.metadata before create_all runs.
from app.models import project, task, milestone, tag, comment  # noqa: F401

# CI sets DATABASE_URL to PostgreSQL on localhost:5432 (per AGENTS.md).
# Locally, default to in-process SQLite for a friction-free `pytest` run.
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./test_dclaw_project.db",
)

_is_sqlite = TEST_DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # SQLite test DB: use a file so multiple connections see the same schema
    # (in-memory needs StaticPool for that — file is simpler + cleared per session).
    db_file = TEST_DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    if db_file.startswith("./"):
        db_file = db_file[2:]
    if db_file and os.path.exists(db_file):
        os.remove(db_file)
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"check_same_thread": False},
    )
else:
    test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)


async def override_get_db():
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
