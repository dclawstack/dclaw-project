import os
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from app.api.main import app
from app.core.database import get_db
from app.models.base import Base
# Ensure all models are registered on Base.metadata before create_all runs.
from app.models import user, workspace, project, task, milestone, tag, comment  # noqa: F401

# CI sets DATABASE_URL to PostgreSQL on localhost:5432 (per AGENTS.md).
# Locally, default to in-process SQLite for a friction-free `pytest` run.
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./test_dclaw_project.db",
)

_is_sqlite = TEST_DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # SQLite test DB: file-backed so multiple connections see the same schema.
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


@pytest_asyncio.fixture(autouse=True)
async def _reset_singletons():
    """Drop process-global singletons (EventBus, integration stubs) between
    tests so per-test event loops never see queues bound to a dead loop
    and integration-stub state never bleeds across files."""
    from app.services.event_bus import reset_event_bus
    from app.services.integrations import reset_integrations

    reset_event_bus()
    reset_integrations()
    yield
    reset_event_bus()
    reset_integrations()


@pytest_asyncio.fixture
async def unauthed_client():
    """Raw client with NO Authorization header. Use only for /auth/* tests
    and the unauthenticated-rejection regression tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def client(unauthed_client):
    """The default test client: registers a user, creates a workspace, and
    sets the Bearer token on every subsequent request. The vast majority
    of test cases just want to talk to a logged-in API."""
    resp = await unauthed_client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "Test-Password-1!",
            "full_name": "Alice",
            "workspace_name": "Test Workspace",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    unauthed_client.headers["Authorization"] = f"Bearer {token}"
    # Expose the registered user/workspace for tests that need to assert on them.
    unauthed_client.auth_response = resp.json()  # type: ignore[attr-defined]
    yield unauthed_client


@pytest_asyncio.fixture
async def second_client(unauthed_client):
    """A second authenticated client in a *different* workspace. Used to
    test tenant isolation."""
    resp = await unauthed_client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@example.com",
            "password": "Test-Password-2!",
            "full_name": "Bob",
            "workspace_name": "Other Workspace",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    # Build a separate AsyncClient so the two don't share headers.
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        ac.auth_response = resp.json()  # type: ignore[attr-defined]
        yield ac
