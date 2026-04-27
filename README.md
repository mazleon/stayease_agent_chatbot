# StayEase AI Agent
 
> An AI-powered accommodation booking assistant for Bangladesh's short-term rental market.  
> Built with **LangGraph**, **FastAPI**, **PostgreSQL**, and **Groq / OpenRouter**.
 
---
 
## Table of Contents
 
1. [System Overview](#1-system-overview)
2. [Conversation Flow](#2-conversation-flow)
3. [LangGraph State Design](#3-langgraph-state-design)
4. [Node Design](#4-node-design)
5. [Tool Definitions](#5-tool-definitions)
6. [Database Schema](#6-database-schema)
7. [Project Structure](#7-project-structure)
8. [Setup & Running](#8-setup--running)
---

## 1. System Overview
 
StayEase AI Agent is a conversational booking assistant embedded in the StayEase short-term rental platform in Bangladesh. Guests interact with the agent via natural language (Bengali or English) to search for available accommodations, view property details, and confirm bookings — all without leaving the chat interface. The system is built around a **LangGraph state machine** that classifies each guest message into one of three intents (search, details, book) and routes it to the appropriate tool. A **FastAPI** backend persists conversation history to **PostgreSQL** and exposes a clean REST API consumed by the web/mobile frontend. The LLM reasoning layer runs on **Groq** (llama-3.3-70b-versatile) for low-latency responses, with drop-in support for OpenRouter models.
 
---


---
 
## 2. Conversation Flow
 
**Scenario:** Guest says _"I need a room in Cox's Bazar for 2 nights for 2 guests"_
 
| Step | Actor | Action |
|------|-------|--------|
| **1** | Guest | Sends `POST /api/chat/f47ac10b-.../message` with `{"message": "I need a room in Cox's Bazar for 2 nights for 2 guests"}` |
| **2** | FastAPI | Loads existing conversation history from PostgreSQL `conversations` table (empty for new session). Calls `run_agent()`. |
| **3** | `classify_intent_node` | Scans message for keywords. Matches "need a room" → sets `intent = "search"`. |
| **4** | Router (conditional edge) | `intent == "search"` → sends execution to `agent_node`. |
| **5** | `agent_node` | Calls LLM (Groq) with system prompt + conversation history. LLM extracts: `location="Cox's Bazar"`, `check_in="2025-06-01"`, `check_out="2025-06-03"`, `num_guests=2`. Emits a **tool call** for `search_available_properties`. |
| **6** | `tool_executor_node` | Executes `search_available_properties(location="Cox's Bazar", check_in="2025-06-01", check_out="2025-06-03", num_guests=2)`. Queries DB for available listings. Returns 2 properties with prices in BDT. |
| **7** | `extract_params_node` | Parses ToolMessage JSON → writes `search_results = [{...}, {...}]` into state. |
| **8** | `agent_node` (second pass) | LLM receives tool result. No further tool calls needed. Generates natural-language reply listing both properties with ৳ pricing and star ratings. |
| **9** | Graph ends | Final state returned to FastAPI. `messages[-1].content` = formatted property list. |
| **10** | FastAPI | Persists user message + assistant reply to `conversations.messages` (JSONB). Returns `200 OK` with `MessageResponse`. |
| **11** | Guest | Sees available properties with prices (e.g., Seabreeze Cottage ৳3,800/night, Hillside Family Resort ৳6,500/night). |
 
---
 

### Field rationale
 
| Field | Why it's needed |
|-------|-----------------|
| `conversation_id` | Ties the in-memory graph run to a persistent DB row for history retrieval |
| `messages` | LangGraph's `add_messages` reducer preserves full turn history for multi-turn reasoning |
| `intent` | Single conditional edge source — drives routing without parsing messages again |
| `location / check_in / check_out / num_guests` | Extracted once by LLM; reused if guest refines search without re-specifying all params |
| `listing_id / listing_details` | Cached so the book flow doesn't repeat a DB round-trip to fetch what was already shown |
| `booking_id / booking_confirmed` | Final confirmation state surfaced to the API layer and included in the response metadata |
| `search_results` | Cached list shown to the guest; also available to `book` flow to validate `listing_id` |
| `error_message` | Decouples error detection (tool node) from error presentation (agent node) |
 
---

## 7. Project Structure
 
```
stayease/
├── agent/
│   ├── __init__.py      # Package exports (graph, run_agent, AgentState)
│   ├── state.py         # AgentState TypedDict definition
│   ├── nodes.py         # Node functions + routing helpers
│   ├── tools.py         # @tool definitions with Pydantic schemas
│   └── graph.py         # StateGraph construction + run_agent() helper
├── api/
│   └── main.py          # FastAPI app with both endpoints
├── schema.sql           # PostgreSQL DDL for all 3 tables
├── api.md               # Full API contract with examples
├── requirements.txt     # Python dependencies
└── README.md            # This document
```
 
---