# StayEase API Contract

Complete API documentation for the StayEase AI booking agent.

---

## Table of Contents

1. [Overview](#overview)
2. [Base URL](#base-url)
3. [Authentication](#authentication)
4. [EndPoints](#endpoints)
   - [POST /api/chat/{conversation_id}/message](#post-apichatconversation_idmessage)
   - [GET /api/chat/{conversation_id}/history](#get-apichatconversation_idhistory)
   - [GET /api/conversations](#get-apiconversations)
   - [GET /health](#get-health)
   - [GET /api/model/availability](#get-apimodelavailability)
5. [Error Handling](#error-handling)

---

## 1. Overview

StayEase provides a REST API for conversational accommodation booking. The API accepts natural language messages and returns AI-generated responses with property listings, booking confirmations, or property details.

Base URL: `http://localhost:8000`

All endpoints are prefixed with `/api`. A `conversation_id` is a client-generated UUID (v4).

---

## 2. Base URL

```
http://localhost:8000
```

For production, replace with your deployed URL.

---

## 3. Authentication

Currently, no authentication is required. The API is designed for internal use.

---

## 4. Endpoints

### POST /api/chat/{conversation_id}/message

Send a guest's natural-language message to the AI agent and receive a reply.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| conversation_id | string | Yes | UUID identifying the ongoing conversation session |

**Request Body (application/json):**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| message | string | Yes | 1–2000 characters | The guest's message text |

**Example — Search request:**
```json
{
  "message": "I need a room in Cox's Bazar for 2 nights for 2 guests"
}
```

**Success Response — 200 OK:**
```json
{
  "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "message_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "role": "assistant",
  "content": "Here are available properties in Cox's Bazar for your stay from June 1 to June 3, 2026:\n\n1. **Hillside Family Resort**\n   - Price: ৳6,500 per night (Total: ৳13,000)\n   - Capacity: 6 guests\n   - Rating: 4.9\n\n2. **Cox's Bazar Beachfront Villa**\n   - Price: ৳12,000 per night (Total: ৳24,000)\n   - Capacity: 10 guests\n   - Rating: 4.8\n\nPlease let me know which property you'd like more details about or if you'd like to proceed with a booking!",
  "timestamp": "2026-04-27T10:30:00Z",
  "metadata": {
    "intent": "search",
    "search_results_count": 2,
    "booking_id": null,
    "booking_confirmed": false
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| conversation_id | string | Echoed from path parameter |
| message_id | string | UUID of this specific assistant message |
| role | string | Always "assistant" |
| content | string | The agent's reply in natural language |
| timestamp | string | ISO-8601 UTC timestamp |
| metadata.intent | string | Classified intent: search, details, book, escalate |
| metadata.search_results_count | integer | Number of properties returned (search flow only) |
| metadata.booking_id | string or null | Booking reference if a booking was created |
| metadata.booking_confirmed | boolean | Whether a booking was successfully confirmed |

**Example — Booking confirmation:**

Request:
```json
{
  "message": "Book the first property. Name: John Doe, Phone: +8801711000000"
}
```

Response:
```json
{
  "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "message_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "role": "assistant",
  "content": "Your booking is confirmed!\n\nReference: BKG-20250601-F5D4\nProperty: Hillside Family Resort\nCheck-in: June 1, 2026\nCheck-out: June 3, 2026\nTotal: ৳13,000 for 2 night(s)\n\nYou'll receive an SMS confirmation shortly.",
  "timestamp": "2026-04-27T10:35:00Z",
  "metadata": {
    "intent": "book",
    "booking_id": "BKG-20250601-F5D4",
    "booking_confirmed": true,
    "search_results_count": 0
  }
}
```

---

### GET /api/chat/{conversation_id}/history

Retrieve all messages in a conversation, in chronological order.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| conversation_id | string | Yes | UUID of the conversation to fetch |

**Success Response — 200 OK:**
```json
{
  "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "messages": [
    {
      "message_id": "1a2b3c4d-0000-0000-0000-000000000001",
      "role": "user",
      "content": "I need a room in Cox's Bazar for 2 nights",
      "timestamp": "2026-04-27T10:29:55Z"
    },
    {
      "message_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "role": "assistant",
      "content": "Could you please provide check-in and check-out dates?",
      "timestamp": "2026-04-27T10:30:00Z"
    }
  ],
  "total": 2
}
```

---

### GET /api/conversations

List all conversations ordered by updated_at DESC.

**Success Response — 200 OK:**
```json
{
  "conversations": [
    {
      "conversation_id": "9f3a7c2d-...",
      "last_intent": "search",
      "last_message_preview": "I need a room in Cox's Bazar...",
      "updated_at": "2026-04-27T09:02:41Z"
    }
  ],
  "total": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| conversations | array | List of conversation summaries |
| conversations[].conversation_id | string | UUID of the conversation |
| conversations[].last_intent | string | Intent from metadata |
| conversations[].last_message_preview | string | Last message, truncated to 60 chars |
| conversations[].updated_at | string | ISO-8601 timestamp |
| total | integer | Total conversation count |

---

### GET /health

Simple system health check.

**Success Response — 200 OK:**
```json
{
  "status": "ok",
  "service": "stayease-agent"
}
```

---

### GET /api/model/availability

Check if the configured OpenRouter LLM model is available.

**Success Response — 200 OK:**
```json
{
  "model_name": "openai/gpt-4o-mini",
  "is_available": true,
  "status_detail": "Model is listed and available on OpenRouter.",
  "timestamp": "2026-04-27T16:22:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| model_name | string | ID of the model being used |
| is_available | boolean | Whether the model is reachable |
| status_detail | string | Human-readable status explanation |
| timestamp | string | ISO-8601 UTC timestamp |

---

## 5. Error Handling

| Status | Body | When |
|--------|------|------|
| 400 | {"detail": "conversation_id must not be empty."} | Empty string in path |
| 422 | {"detail": [...]} | Missing or invalid request body fields |
| 500 | {"detail": "Agent error: ..."} | Agent or LLM failure |

### Agent-level errors (handled gracefully):

| Scenario | Example agent reply |
|----------|----------------|
| Invalid listing ID | "Invalid listing ID. Please search for properties first." |
| Listing not found | "Listing not found or is no longer active." |
| Booking conflict | "Property not available for selected dates. Choose different dates." |

---

## HTTP Conventions

- All request/response bodies are `application/json`
- Timestamps are ISO-8601 strings in UTC (Z suffix)
- IDs are UUID v4 strings
- Monetary values are integers in BDT (৳)
- conversation_id must be generated client-side before first call