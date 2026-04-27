"""
webui/api_client.py
--------------------
HTTP client for communicating with the StayEase FastAPI backend.
"""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 120.0



def send_message(conversation_id: str, message: str) -> dict[str, Any]:
    """Send a message to the agent and receive a reply."""
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(
            f"{BASE_URL}/api/chat/{conversation_id}/message",
            json={"message": message},
        )
        response.raise_for_status()
        return response.json()


def get_history(conversation_id: str) -> list[dict[str, Any]]:
    """Retrieve the full message history for a conversation."""
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/api/chat/{conversation_id}/history")
        response.raise_for_status()
        data = response.json()
        return data.get("messages", [])


def list_conversations() -> list[dict[str, Any]]:
    """List all conversations ordered by updated_at DESC."""
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/api/conversations")
        response.raise_for_status()
        data = response.json()
        return data.get("conversations", [])


def check_health() -> bool:
    """Check if the backend is running."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BASE_URL}/health")
            return response.status_code == 200
    except Exception:
        return False


def get_model_availability() -> dict[str, Any]:
    """Check if the configured LLM model is available."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{BASE_URL}/api/model/availability")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {
            "model_name": "unknown",
            "is_available": False,
            "status_detail": f"Error: {str(e)}",
            "timestamp": None
        }