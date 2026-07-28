"""Pytest configuration for test suite - handles database mocking during collection."""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg

def pytest_configure(config):
    """Configure pytest before collection - patch asyncpg early."""
    # Mock asyncpg.create_pool to prevent connection attempts during module import
    original_create_pool = asyncpg.create_pool

    async def mock_create_pool(*args, **kwargs):
        """Mock asyncpg pool that returns a fake database."""
        db = MagicMock()
        db.execute = AsyncMock(return_value="OK")
        db.fetchval = AsyncMock(return_value=1)
        db.fetch = AsyncMock(return_value=[])
        db.fetchrow = AsyncMock(return_value=None)
        db.close = AsyncMock(return_value=None)
        return db

    asyncpg.create_pool = mock_create_pool
