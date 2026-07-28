"""Pytest configuration - prevents database connection attempts during collection."""
import sys
from unittest.mock import AsyncMock, MagicMock

def pytest_configure(config):
    """Patch asyncpg.create_pool BEFORE test collection to prevent connection errors."""
    def _fake_db():
        db = MagicMock()
        db.execute = AsyncMock(return_value="OK")
        db.fetchval = AsyncMock(return_value=1)
        db.fetch = AsyncMock(return_value=[])
        db.fetchrow = AsyncMock(return_value=None)
        return db

    # Create a proper mock for asyncpg.create_pool
    async def _mock_create_pool(*args, **kwargs):
        return _fake_db()

    # Patch asyncpg BEFORE importing hermes_agents
    import asyncpg
    asyncpg.create_pool = AsyncMock(side_effect=_mock_create_pool)
