# StayEase Streamlit Web UI — Design Spec

**Date:** 2026-04-27  
**Status:** Approved  

---

## Overview

A Streamlit chat UI for the StayEase AI booking agent. Integrates with the existing FastAPI backend at `http://localhost:8000`. Users can start new conversations, switch between past ones via a sidebar, and see special rendering for booking confirmations.

---

## File Structure

```
webui/
├── app.py           # Streamlit entry point — sidebar + chat rendering
├── api_client.py    # All HTTP calls to FastAPI (no URL construction in app.py)
└── requirements.txt # streamlit, httpx
```

---

## New Backend Endpoint

**`GET /api/conversations`** added to `api/main.py`.

Queries the `conversations` table and returns a list ordered by `updated_at DESC`:

```json
[
  {
    "conversation_id": "9f3a7c2d...",
    "last_intent": "search",
    "last_message_preview": "I need a room in Cox's Bazar...",
    "updated_at": "2026-04-27T09:02:41Z"
  }
]
```

- `last_intent` — from `metadata->>'intent'` (nullable)
- `last_message_preview` — content of the last element in `messages` JSONB, truncated to 60 chars
- Returns empty list `[]` if no conversations exist yet

---

## UI Layout

### Sidebar (left, ~240px)
- StayEase logo + subtitle
- **"+ New Conversation"** button — generates a new UUID, clears `st.session_state.messages`
- **"Recent Conversations"** list — one item per conversation, fetched from `GET /api/conversations` on every rerun
  - Each item shows: last message preview, relative timestamp, intent badge
  - Clicking an item sets `conversation_id` and loads history from `GET /api/chat/{id}/history`
  - Active conversation is highlighted

### Intent badge colours
| Intent | Colour |
|--------|--------|
| `search` | green |
| `book` | blue |
| `details` | purple |
| `escalate` | red |
| `unknown` / null | grey |

### Main panel (right)
- **Header bar** — "StayEase AI Booking Assistant" + truncated conversation ID
- **Message area** — scrollable; user bubbles right-aligned (blue), agent bubbles left-aligned (white)
- **Booking confirmation card** — rendered instead of a plain bubble when `metadata.booking_confirmed == true`; shows reference, property, dates, total price in BDT
- **Chat input** — `st.chat_input` at bottom; disabled with spinner while agent is responding

---

## State Management

| Key | Type | Purpose |
|-----|------|---------|
| `st.session_state.conversation_id` | `str` | UUID of the active conversation |
| `st.session_state.messages` | `list[dict]` | Local message list for instant rendering |

### Message dict shape (mirrors DB + API)
```python
{
    "role": "user" | "assistant",
    "content": str,
    "timestamp": str,          # ISO-8601
    "metadata": dict | None    # only on assistant messages
}
```

### Send message flow
1. Append user message to `st.session_state.messages` immediately
2. Show spinner
3. Call `POST /api/chat/{conversation_id}/message`
4. Append assistant reply (with metadata) to `st.session_state.messages`
5. Streamlit reruns — sidebar conversation list refreshes automatically

### Switch conversation flow
1. Set `st.session_state.conversation_id`
2. Call `GET /api/chat/{id}/history`
3. Map history records to message dicts, store in `st.session_state.messages`

---

## api_client.py — Function Signatures

```python
def send_message(conversation_id: str, message: str) -> dict
def get_history(conversation_id: str) -> list[dict]
def list_conversations() -> list[dict]
```

All functions use `httpx` with a `BASE_URL` constant (defaults to `http://localhost:8000`). On HTTP error, return an empty result or raise — caught in `app.py` with `st.error()`.

---

## Error Handling

- Network / 500 errors → `st.error("Could not reach the agent. Is the backend running?")`, message not appended
- Empty conversation list → sidebar shows "No conversations yet" placeholder
- History load failure → `st.warning(...)`, `messages` stays empty

---

## Dependencies (`webui/requirements.txt`)

```
streamlit>=1.35.0
httpx>=0.28.0
python-dotenv>=1.0.0
```

`python-dotenv` allows `BASE_URL` to be overridden via a `.env` file in `webui/`.
