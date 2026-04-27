"""
StayEase FastAPI Backend
-------------------------
Exposes two endpoints:
  POST /api/chat/{conversation_id}/message   — send a guest message
  GET  /api/chat/{conversation_id}/history   — retrieve conversation history
"""

from __future__ import annotations

import uuid
import os
import httpx
from datetime import datetime, timezone
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.graph import run_agent
from db import close_pool
from db.conversations import get_conversation_history, save_conversation_message, update_conversation_metadata, list_conversations



class ModelAvailabilityResponse(BaseModel):
    model_name: str
    is_available: bool
    status_detail: str
    timestamp: datetime

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pool is lazily initialized on first use
    yield
    # Shutdown: clean up pool
    await close_pool()

app = FastAPI(
    title="StayEase AI Agent API",
    description="AI-powered accommodation booking agent for Bangladesh.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The guest's message text.",
        examples=["I need a room in Cox's Bazar for 2 nights for 2 guests"],
    )


class MessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    role: str = Field(..., description="'assistant'")
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(BaseModel):
    message_id: str
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    timestamp: datetime


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ConversationMessage]
    total: int


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# POST /api/chat/{conversation_id}/message
# ---------------------------------------------------------------------------


@app.post(
    "/api/chat/{conversation_id}/message",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Agent error"},
    },
    summary="Send a guest message",
    tags=["Chat"],
)
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
) -> MessageResponse:
    """
    Send a guest message to the StayEase AI agent and receive a reply.
    """
    if not conversation_id.strip():
        raise HTTPException(status_code=400, detail="conversation_id must not be empty.")

    # Retrieve existing history from DB
    history = await get_conversation_history(conversation_id)

    # Persist the user message
    user_msg: dict[str, Any] = {
        "message_id": str(uuid.uuid4()),
        "role": "user",
        "content": body.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await save_conversation_message(conversation_id, user_msg)

    # Run agent
    try:
        # Convert DB history to LangGraph format
        lang_history = [
            {"type": "human" if m["role"] == "user" else "ai", "content": m["content"]}
            for m in history
        ]
        
        final_state = await run_agent(
            conversation_id=conversation_id,
            user_message=body.message,
            history=lang_history,
        )
        
        agent_reply = final_state["messages"][-1].content
        extra_meta = {
            "intent": final_state.get("intent"),
            "booking_id": final_state.get("booking_id"),
            "booking_confirmed": final_state.get("booking_confirmed"),
            "search_results_count": len(final_state.get("search_results", [])),
        }

    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {exc}",
        ) from exc

    # Persist assistant reply
    assistant_msg: dict[str, Any] = {
        "message_id": str(uuid.uuid4()),
        "role": "assistant",
        "content": agent_reply,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra_meta,
    }
    await save_conversation_message(conversation_id, assistant_msg)
    
    # Update conversation metadata in DB
    await update_conversation_metadata(conversation_id, extra_meta)

    return MessageResponse(
        conversation_id=conversation_id,
        message_id=assistant_msg["message_id"],
        role="assistant",
        content=agent_reply,
        timestamp=datetime.fromisoformat(assistant_msg["timestamp"]),
        metadata=extra_meta,
    )


# ---------------------------------------------------------------------------
# GET /api/chat/{conversation_id}/history
# ---------------------------------------------------------------------------


@app.get(
    "/api/chat/{conversation_id}/history",
    response_model=ConversationHistoryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
    summary="Get conversation history",
    tags=["Chat"],
)
async def get_history(conversation_id: str) -> ConversationHistoryResponse:
    """
    Retrieve the full message history for a conversation.
    """
    if not conversation_id.strip():
        raise HTTPException(status_code=400, detail="conversation_id must not be empty.")

    history = await get_conversation_history(conversation_id)

    messages = [
        ConversationMessage(
            message_id=m["message_id"],
            role=m["role"],
            content=m["content"],
            timestamp=datetime.fromisoformat(m["timestamp"]),
        )
        for m in history
    ]

    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=messages,
        total=len(messages),
    )


# ---------------------------------------------------------------------------
# GET /api/conversations
# ---------------------------------------------------------------------------


class ConversationSummary(BaseModel):
    conversation_id: str
    last_intent: str | None = None
    last_message_preview: str | None = None
    updated_at: str | None = None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int


@app.get(
    "/api/conversations",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all conversations",
    tags=["Chat"],
)
async def get_conversations() -> ConversationListResponse:
    """
    List all conversations ordered by updated_at DESC.
    """
    convos = await list_conversations()
    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                conversation_id=c["conversation_id"],
                last_intent=c["last_intent"],
                last_message_preview=c["last_message_preview"],
                updated_at=c["updated_at"],
            )
            for c in convos
        ],
        total=len(convos),
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "stayease-agent"}


@app.get(
    "/api/model/availability",
    response_model=ModelAvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Check LLM model availability from OpenRouter",
    tags=["System"],
)
async def get_model_availability() -> ModelAvailabilityResponse:
    """
    Check if the configured OpenRouter model is currently available.
    """
    model_name = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-6")
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        return ModelAvailabilityResponse(
            model_name=model_name,
            is_available=False,
            status_detail="OpenRouter API key missing.",
            timestamp=datetime.now(timezone.utc),
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://openrouter.ai/api/v1/models")
            if response.status_code != 200:
                return ModelAvailabilityResponse(
                    model_name=model_name,
                    is_available=False,
                    status_detail=f"OpenRouter API returned error: {response.status_code}",
                    timestamp=datetime.now(timezone.utc),
                )

            models_data = response.json().get("data", [])
            found = any(m.get("id") == model_name for m in models_data)

            if found:
                return ModelAvailabilityResponse(
                    model_name=model_name,
                    is_available=True,
                    status_detail="Model is listed and available on OpenRouter.",
                    timestamp=datetime.now(timezone.utc),
                )
            else:
                return ModelAvailabilityResponse(
                    model_name=model_name,
                    is_available=False,
                    status_detail="Model not found in OpenRouter's active models list.",
                    timestamp=datetime.now(timezone.utc),
                )
    except Exception as e:
        return ModelAvailabilityResponse(
            model_name=model_name,
            is_available=False,
            status_detail=f"Error checking availability: {str(e)}",
            timestamp=datetime.now(timezone.utc),
        )
