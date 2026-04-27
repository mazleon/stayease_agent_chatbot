# StayEase API Contract

Two HTTP endpoints power the guest-facing chat interface.

---

## Base URL

```
http://localhost:8000
```

All endpoints are prefixed with `/api/chat/{conversation_id}`.  
A `conversation_id` is a client-generated UUID (v4).

---

## Endpoint 1 — Send a guest message

### `POST /api/chat/{conversation_id}/message`

Send a guest's natural-language message to the AI agent and receive a reply.

---

### Path Parameters

| Parameter         | Type   | Required | Description                                      |
|-------------------|--------|----------|--------------------------------------------------|
| `conversation_id` | string | ✅        | UUID identifying the ongoing conversation session |

---

### Request Body (`application/json`)

| Field     | Type   | Required | Constraints        | Description               |
|-----------|--------|----------|--------------------|---------------------------|
| `message` | string | ✅        | 1–2000 characters  | The guest's message text  |

#### Example — Search request

```json
{
  "message": "আমি Cox's Bazar-এ ২ রাতের জন্য ২ জন গেস্টের জন্য একটা রুম চাই"
}
```

---

### Success Response — `200 OK`

```json
{
  "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "message_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "role": "assistant",
  "content": "আমি Cox's Bazar-এ আপনার জন্য ২টি উপলব্ধ সম্পত্তি খুঁজে পেয়েছি:\n\n🏠 **Seabreeze Cottage** — ৳3,800/রাত (মোট ৳7,600)\n   ✅ WiFi, AC, Breakfast Included, Sea View | ⭐ 4.6\n\n🏠 **Hillside Family Resort** — ৳6,500/রাত (মোট ৳13,000)\n   ✅ WiFi, AC, Pool, Kitchen, Parking | ⭐ 4.9\n\nকোনো সম্পত্তির বিস্তারিত জানতে চাইলে বলুন!",
  "timestamp": "2025-06-01T10:30:00Z",
  "metadata": {
    "intent": "search",
    "search_results_count": 2,
    "booking_id": null
  }
}
```

#### Response fields

| Field             | Type     | Description                                                    |
|-------------------|----------|----------------------------------------------------------------|
| `conversation_id` | string   | Echoed from path parameter                                     |
| `message_id`      | string   | UUID of this specific assistant message                        |
| `role`            | string   | Always `"assistant"`                                           |
| `content`         | string   | The agent's reply in natural language                          |
| `timestamp`       | string   | ISO-8601 UTC timestamp                                         |
| `metadata.intent` | string   | Classified intent: `search` \| `details` \| `book` \| `escalate` |
| `metadata.search_results_count` | integer | Number of properties returned (search flow only) |
| `metadata.booking_id` | string \| null | Booking reference if a booking was created       |

---

### Example — Booking confirmation

**Request:**
```json
{
  "message": "Seabreeze Cottage বুক করুন। আমার নাম Farhan Ahmed, ফোন 01711234567।"
}
```

**Response (`200 OK`):**
```json
{
  "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "message_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "role": "assistant",
  "content": "✅ বুকিং নিশ্চিত হয়েছে! আপনার রেফারেন্স নম্বর: **BKG-20250601-A3F2**\n\n📍 Seabreeze Cottage, Cox's Bazar\n📅 Check-in: 1 জুন 2025 | Check-out: 3 জুন 2025\n👥 2 জন গেস্ট | 2 রাত\n💰 মোট: ৳7,600\n\nশীঘ্রই আপনার ফোনে SMS নিশ্চিতকরণ পাঠানো হবে। 🙏",
  "timestamp": "2025-06-01T10:35:00Z",
  "metadata": {
    "intent": "book",
    "booking_id": "BKG-20250601-A3F2",
    "search_results_count": 0
  }
}
```

---

### Error Responses

| Status | Body                                                                 | When                                      |
|--------|----------------------------------------------------------------------|-------------------------------------------|
| `422`  | `{"error": "Validation error", "detail": "message: field required"}` | Missing or invalid request body fields    |
| `500`  | `{"error": "Agent error", "detail": "LLM timeout after 30s"}`        | Agent or LLM failure                      |

---

---

## Endpoint 2 — Get conversation history

### `GET /api/chat/{conversation_id}/history`

Retrieve all messages in a conversation, in chronological order.

---

### Path Parameters

| Parameter         | Type   | Required | Description                        |
|-------------------|--------|----------|------------------------------------|
| `conversation_id` | string | ✅        | UUID of the conversation to fetch  |

No request body or query parameters.

---

### Success Response — `200 OK`

```json
{
  "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "messages": [
    {
      "message_id": "1a2b3c4d-0000-0000-0000-000000000001",
      "role": "user",
      "content": "আমি Cox's Bazar-এ ২ রাতের জন্য একটা রুম চাই, ২ জন গেস্ট।",
      "timestamp": "2025-06-01T10:29:55Z"
    },
    {
      "message_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "role": "assistant",
      "content": "আমি Cox's Bazar-এ আপনার জন্য ২টি উপলব্ধ সম্পত্তি খুঁজে পেয়েছি:\n\n🏠 **Seabreeze Cottage** — ৳3,800/রাত...",
      "timestamp": "2025-06-01T10:30:00Z"
    },
    {
      "message_id": "2c3d4e5f-0000-0000-0000-000000000003",
      "role": "user",
      "content": "Seabreeze Cottage সম্পর্কে আরও জানতে চাই।",
      "timestamp": "2025-06-01T10:31:10Z"
    },
    {
      "message_id": "3d4e5f60-0000-0000-0000-000000000004",
      "role": "assistant",
      "content": "🏠 **Seabreeze Cottage** — বিস্তারিত তথ্য:\n\n📍 Plot 12, Kolatoli Beach Road, Cox's Bazar-4700\n💰 ৳3,800/রাত | 👥 সর্বোচ্চ 4 জন\n🛏 2 বেডরুম | 🚿 1 বাথরুম\n✅ সুবিধা: WiFi, AC, Breakfast Included, Sea View, Hot Water\n📋 নিয়ম: ধূমপান নিষিদ্ধ। Check-in বিকাল ২টার পর।\n↩️ বাতিল নীতি: Check-in-এর ৪৮ ঘন্টা আগে বিনামূল্যে বাতিল।\n⭐ 4.6 (38 রিভিউ) | হোস্ট: Rahim Uddin",
      "timestamp": "2025-06-01T10:31:15Z"
    }
  ],
  "total": 4
}
```

#### Response fields

| Field             | Type             | Description                                          |
|-------------------|------------------|------------------------------------------------------|
| `conversation_id` | string           | Echoed UUID                                          |
| `messages`        | array of objects | All messages, oldest first                           |
| `messages[].message_id` | string   | Unique UUID per message                              |
| `messages[].role` | string           | `"user"` or `"assistant"`                            |
| `messages[].content` | string        | Message text                                         |
| `messages[].timestamp` | string      | ISO-8601 UTC                                         |
| `total`           | integer          | Total message count                                  |

---

### Error Responses

| Status | Body                                                                                      | When                                     |
|--------|-------------------------------------------------------------------------------------------|------------------------------------------|
| `404`  | `{"error": "Not found", "detail": "Conversation 'f47ac10b-...' not found."}`              | `conversation_id` does not exist in DB   |

---

## HTTP Conventions

- All request and response bodies are `application/json`.
- Timestamps are ISO-8601 strings in UTC (`Z` suffix).
- IDs are UUID v4 strings.
- Monetary values are always integers in BDT (Bangladeshi Taka, ৳). No decimals.
- A new `conversation_id` must be generated client-side (UUID v4) before calling `POST /message` for the first time.
- Clients should include `Content-Type: application/json` on POST requests.