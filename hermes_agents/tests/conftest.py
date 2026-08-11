"""pytest configuration for hermes_agents tests."""
import sys
import os
from unittest.mock import AsyncMock
import asyncpg

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock asyncpg.create_pool before any modules are imported
original_create_pool = asyncpg.create_pool

async def mock_create_pool(*args, **kwargs):
    """Mock database pool that prevents actual connections during tests."""
    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    return mock_pool

asyncpg.create_pool = mock_create_pool
