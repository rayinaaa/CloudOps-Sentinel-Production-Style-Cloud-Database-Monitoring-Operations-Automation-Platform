"""Pytest configuration and test fixtures."""

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine


@pytest_asyncio.fixture
async def client():
    """Async test client for invoking FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    # Cleanly dispose pool to prevent cross-event-loop connection reuse
    await engine.dispose()
