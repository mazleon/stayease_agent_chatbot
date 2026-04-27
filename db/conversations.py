"""
db/conversations.py
--------------------
Handles persistence of chat history using the conversations and
conversation_messages tables (one row per message, no JSONB array).
"""

import json
import uuid
from typing import Any

from db import get_pool


async def get_conversation_history(conversation_id: str) -> list[dict[str, Any]]:
    """Return all messages for a conversation ordered by creation time."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT message_id, role, content, metadata, created_at
            FROM conversation_messages
            WHERE conversation_id = $1::text
            ORDER BY created_at ASC
            """,
            conversation_id,
        )
        return [
            {
                "message_id": row["message_id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["created_at"].isoformat(),
                **(
                    row["metadata"]
                    if isinstance(row["metadata"], dict)
                    else json.loads(row["metadata"] or "{}")
                ),
            }
            for row in rows
        ]


async def save_conversation_message(conversation_id: str, message: dict[str, Any]):
    """
    Persist a single message atomically.

    Creates the parent conversations row if it doesn't exist yet.
    Extra keys beyond role/content/message_id/timestamp are stored as
    message-level metadata (intent, booking_id, etc.).
    """
    role = message["role"]
    content = message["content"]
    message_id = message.get("message_id") or str(uuid.uuid4())

    skip = {"role", "content", "message_id", "timestamp"}
    extra = {k: v for k, v in message.items() if k not in skip}

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO conversations (id, updated_at)
                VALUES ($1::text, NOW())
                ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
                """,
                conversation_id,
            )
            await conn.execute(
                """
                INSERT INTO conversation_messages
                    (conversation_id, message_id, role, content, metadata)
                VALUES ($1::text, $2, $3, $4, $5::jsonb)
                ON CONFLICT (message_id) DO NOTHING
                """,
                conversation_id,
                message_id,
                role,
                content,
                json.dumps(extra),
            )


async def update_conversation_metadata(conversation_id: str, metadata: dict[str, Any]):
    """Merge new key-value pairs into the conversation's metadata JSONB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE conversations SET metadata = metadata || $2::jsonb WHERE id = $1::text",
            conversation_id,
            json.dumps(metadata),
        )


async def list_conversations() -> list[dict[str, Any]]:
    """Return all conversations with last-message preview, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id       AS conversation_id,
                c.metadata,
                c.updated_at,
                lm.content AS last_content
            FROM conversations c
            LEFT JOIN LATERAL (
                SELECT content
                FROM conversation_messages
                WHERE conversation_id = c.id
                ORDER BY created_at DESC
                LIMIT 1
            ) lm ON TRUE
            ORDER BY c.updated_at DESC
            """,
        )
        result = []
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            text = row["last_content"]
            preview = (text[:60] + "...") if text and len(text) > 60 else text
            result.append({
                "conversation_id": row["conversation_id"],
                "last_intent": (meta or {}).get("intent"),
                "last_message_preview": preview,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            })
        return result
