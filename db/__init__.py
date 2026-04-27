"""
StayEase Database Layer
-----------------------
Exports the asyncpg connection pool manager.
Use `get_pool()` to obtain a pool and `close_pool()` on app shutdown.
"""

from db.pool import close_pool, get_pool

__all__ = ["get_pool", "close_pool"]
