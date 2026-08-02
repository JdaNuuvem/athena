"""Pytest configuration with database mocking."""
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# Import asyncpg first to ensure it's loaded before patching
try:
    import asyncpg
except ImportError:
    pass

class MockConnectionPool:
    """Mock pool that records queries and responds with dummy data."""

    async def execute(self, query, *params):
        return "OK"

    async def fetchval(self, query, *params):
        return 0

    async def fetchrow(self, query, *params):
        return None

    async def fetch(self, query, *params):
        return []

    class _MockConnection:
        async def execute(self, query, *params):
            return "OK"
        async def fetchval(self, query, *params):
            return 0
        async def fetchrow(self, query, *params):
            return None
        async def fetch(self, query, *params):
            return []

        class _MockTransaction:
            async def __aenter__(self):
                return None
            async def __aexit__(self, *args):
                pass

        def transaction(self):
            return self._MockTransaction()

    class _MockAcquire:
        def __init__(self):
            self._conn = MockConnectionPool._MockConnection()

        async def __aenter__(self):
            return self._conn

        async def __aexit__(self, *args):
            pass

    def acquire(self):
        return self._MockAcquire()

_MOCK_POOL = MockConnectionPool()

async def _mock_create_pool(*args, **kwargs):
    """Mock factory for asyncpg.create_pool"""
    return _MOCK_POOL

# Apply the patch at module import time before any other imports
patch("asyncpg.create_pool", new=_mock_create_pool).start()
