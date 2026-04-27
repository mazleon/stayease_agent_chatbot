"""
tests/test_api.py
------------------
Automated tests for the StayEase API using httpx.AsyncClient.
This is the correct way to test async FastAPI apps to avoid event loop issues.
"""

import uuid
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from api.main import app
from db import close_pool

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def cleanup_pool():
    yield
    await close_pool()

@pytest.mark.asyncio(scope="session")
async def test_health_check():
    """Test the health check endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "stayease-agent"}

@pytest.mark.asyncio(scope="session")
async def test_api_chat_flow():
    """Test a full chat flow: message -> history."""
    conversation_id = str(uuid.uuid4())
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Send a message (with retry logic for 429 rate limits)
        payload = {"message": "Hello, I'm looking for a room in Sylhet."}
        
        for attempt in range(5):
            response = await ac.post(f"/api/chat/{conversation_id}/message", json=payload)
            if response.status_code == 500 and "429" in str(response.json()):
                import asyncio
                print(f"Upstream rate limit (429). Retrying attempt {attempt + 1}...")
                await asyncio.sleep(2 ** attempt)
                continue
            break
        
        if response.status_code != 200:
            print(f"Error detail: {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conversation_id
        assert "content" in data
        assert data["role"] == "assistant"
        assert "intent" in data.get("metadata", {})

        # 2. Check history
        response = await ac.get(f"/api/chat/{conversation_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conversation_id
        assert data["total"] >= 2  # user msg + agent reply
        
        messages = data["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == payload["message"]
        assert messages[1]["role"] == "assistant"

@pytest.mark.asyncio(scope="session")
async def test_string_conversation_id():
    """Test that non-UUID string IDs are accepted (API accepts any non-empty string)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/chat/not-a-uuid/history")
    assert response.status_code == 200
    assert response.json()["total"] == 0

@pytest.mark.asyncio(scope="session")
async def test_non_existent_conversation():
    """Test history for a new but valid UUID."""
    new_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/chat/{new_id}/history")
    assert response.status_code == 200
    assert response.json()["total"] == 0
