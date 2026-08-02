# apps/api/tests/conftest.py
import os
import shutil
import tempfile

_tmp = tempfile.mkdtemp(prefix="estudiohc_test_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["API_KEY"] = "test-key"
os.environ["RATE_LIMIT_PER_MIN"] = "10000"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.database import init_db
from src.main import app


@pytest_asyncio.fixture(scope="session")
async def _setup_db():
    await init_db()
    yield
    shutil.rmtree(_tmp, ignore_errors=True)


@pytest_asyncio.fixture
async def client(_setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
