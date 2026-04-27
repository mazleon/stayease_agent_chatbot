"""
db/conversations.py
--------------------
Handles persistence of chat history in the `conversations` table.
"""

import json
from datetime import datetime
from typing import Any
import asyncpg
from db import get_pool

async def get_conversation_history(conversation_id: str) -> list[dict[str, Any]]:
    """Retrieve history from the DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # We use the conversation_id (UUID) to find the record.
        # If it doesn't exist, return empty list.
        row = await conn.fetchrow(
            "SELECT messages FROM conversations WHERE id = $1::uuid",
            conversation_id
        )
        if row:
            return json.loads(row["messages"])
        return []

async def save_conversation_message(conversation_id: str, message: dict[str, Any]):
    """Append a message to the conversation history in DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Use an UPSERT style approach
        history = await get_conversation_history(conversation_id)
        history.append(message)
        
        await conn.execute(
            """
            INSERT INTO conversations (id, messages, updated_at)
            VALUES ($1::uuid, $2::jsonb, NOW())
            ON CONFLICT (id) DO UPDATE
            SET messages = $2::jsonb, updated_at = NOW()
            """,
            conversation_id,
            json.dumps(history)
        )

async def update_conversation_metadata(conversation_id: str, metadata: dict[str, Any]):
    """Update metadata for a conversation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE conversations SET metadata = metadata || $2::jsonb WHERE id = $1::uuid",
            conversation_id,
            json.dumps(metadata)
        )
