"""
db/pool.py
----------
Lazily initialised asyncpg connection pool.

Usage in async context:
    from db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT ...")

The pool is created once per process and reused across all requests.
Call close_pool() on application shutdown (FastAPI lifespan, test teardown, etc.).
"""

from __future__ import annotations

import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the singleton asyncpg pool, creating it on first call."""
    global _pool  # noqa: PLW0603

    if _pool is not None:
        return _pool

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your .env file:\n"
            "  DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require"
        )

    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
        # asyncpg requires ssl=True for Neon's ?sslmode=require
        ssl=True,
    )
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool. Call this in your app shutdown handler."""
    global _pool  # noqa: PLW0603

    if _pool is not None:
        await _pool.close()
        _pool = None
