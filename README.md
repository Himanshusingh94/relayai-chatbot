# RelayAI

RelayAI is a resilient full-stack AI chatbot built with **FastAPI, LiteLLM, SQLite, React, and Docker**.

It supports multi-turn conversations, automatic LLM provider failover, response caching, persistent conversation history, token usage tracking, latency metadata, and a clean React chat interface.

---

## Features

- Multi-turn AI conversations
- Persistent conversation history using SQLite
- Multiple LLM providers through LiteLLM
- Automatic provider/key failover
- Gemini as the primary provider
- Groq as the fallback provider
- Retry handling for `429`, quota, and `5xx` failures
- LiteLLM response caching
- Per-request input/output token usage
- Request latency tracking
- Optional system prompt support
- Failure simulation for testing
- React chat interface
- Dockerized frontend and backend
- Persistent Docker volume for SQLite
- Automated backend tests

---

## Architecture

```text
                    ┌──────────────────────┐
                    │      React UI        │
                    │    localhost:3000    │
                    └──────────┬───────────┘
                               │
                               │ POST /chat
                               ▼
                    ┌──────────────────────┐
                    │      FastAPI         │
                    │    localhost:8000    │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 ▼             ▼             ▼
              SQLite        LiteLLM       LLM Cache
           /data/app.db        │
                               │
                         ┌─────┴─────┐
                         │           │
                         ▼           ▼
                      Gemini       Groq
                       key_1       key_2
                         │           ▲
                         │ failure   │
                         └───────────┘
                           failover
```

---

## LLM Failover

RelayAI maintains an ordered provider pool.

Current configuration:

```text
key_1 → Gemini
key_2 → Groq
```

The backend first attempts the primary provider.

If the request fails because of a retryable error such as:

- HTTP `429`
- Quota/rate-limit errors
- HTTP `500`
- HTTP `502`
- HTTP `503`

RelayAI automatically attempts the next configured provider.

Example:

```text
User Request
     ↓
Gemini / key_1
     ↓
503 Service Unavailable
     ↓
Groq / key_2
     ↓
Successful Response
```

If the fallback provider succeeds, the client still receives HTTP `200`.

Example metadata:

```json
{
  "resolution_source": "LIVE_INFERENCE",
  "model": "groq/openai/gpt-oss-120b",
  "latency_ms": 452,
  "input_tokens": 85,
  "output_tokens": 42,
  "key_id": "key_2",
  "fallback_attempts": 1
}
```

If all providers fail, the API returns HTTP `503`:

```json
{
  "detail": "all providers unavailable"
}
```

Failed requests are not added to conversation history.

---

## Response Caching

RelayAI uses LiteLLM's built-in response cache.

The cache is based on the LLM request, including the model and complete message list.

A new request is resolved using live inference:

```json
{
  "resolution_source": "LIVE_INFERENCE"
}
```

An identical request can subsequently be served from cache:

```json
{
  "resolution_source": "LLM_CACHE",
  "key_id": null,
  "fallback_attempts": 0
}
```

Cached responses preserve the original token usage information.

---

## Multi-Turn Conversations

The frontend sends the newest user message along with a session ID.

RelayAI stores previous messages in SQLite and reconstructs the conversation before calling the LLM.

Example:

```text
User: Remember the number 7392.

AI: OK

User: What number did I ask you to remember?

AI: 7392
```

Conversation history is persisted in SQLite.

---

## Project Structure

```text
relayai-chatbot/
│
├── backend/
│   ├── tests/
│   │   └── test_api.py
│   ├── .dockerignore
│   ├── .gitignore
│   ├── Dockerfile
│   ├── database.py
│   ├── llm_service.py
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.css
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.js
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## Environment Variables

Create `backend/.env` using the variables shown in `.env.example`.

Example:

```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key

GEMINI_MODEL=gemini/gemini-3.8-flash
GROQ_MODEL=groq/openai/gpt-oss-120b

DATABASE_URL=sqlite:////data/app.db
ALLOWED_ORIGINS=http://localhost:3000
ENABLE_FAILURE_SIMULATION=true
```

Replace the placeholder API keys with your own credentials.

> **Important:** Never commit real API keys. `backend/.env` is ignored by Git.

---

## Running with Docker

### Requirements

Install:

- Docker
- Docker Compose

Start the complete application:

```bash
docker compose up --build -d
```

On systems with GNU Make, you can also run:

```bash
make up
```

The application will be available at:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
Health:   http://localhost:8000/health
```

Stop the application:

```bash
docker compose down
```

or:

```bash
make down
```

Do not use:

```bash
docker compose down -v
```

if you want to preserve the SQLite database volume.

---

## SQLite Persistence

Docker Compose mounts a named volume at:

```text
/data
```

The SQLite database is stored at:

```text
/data/app.db
```

This allows conversation history to survive container recreation.

```text
docker compose down
        ↓
containers removed
        ↓
docker compose up
        ↓
conversation history remains
```

---

# API Documentation

## Health Check

### Request

```http
GET /health
```

### Example Response

```json
{
  "status": "ok",
  "keys_configured": 2,
  "cache_enabled": true
}
```

---

## Send a Chat Message

### Request

```http
POST /chat
Content-Type: application/json
```

Example body:

```json
{
  "session_id": "demo-session",
  "message": "Hello",
  "system_prompt": "Answer concisely"
}
```

### Example Response

```json
{
  "session_id": "demo-session",
  "reply": "Hello! How can I help?",
  "metadata": {
    "resolution_source": "LIVE_INFERENCE",
    "model": "groq/openai/gpt-oss-120b",
    "latency_ms": 452,
    "input_tokens": 85,
    "output_tokens": 42,
    "key_id": "key_2",
    "fallback_attempts": 1
  }
}
```

---

## Retrieve Session History

### Request

```http
GET /sessions/{session_id}/messages
```

Example:

```http
GET /sessions/demo-session/messages
```

Unknown sessions return HTTP `404`:

```json
{
  "detail": "session not found"
}
```

---

# Failure Simulation

When:

```env
ENABLE_FAILURE_SIMULATION=true
```

the backend supports the `X-Simulate-Failure` request header.

This feature is intended for testing failover behavior.

## Force Primary Provider Failure

Send:

```text
X-Simulate-Failure: key_1=429
```

Expected behavior:

```text
key_1
  ↓
simulated 429
  ↓
key_2
  ↓
success
```

Response metadata should include:

```json
{
  "key_id": "key_2",
  "fallback_attempts": 1
}
```

---

## Simulate Multiple Provider Failures

Example:

```text
X-Simulate-Failure: key_1=429,key_2=503
```

---

## Fail Every Provider

Send:

```text
X-Simulate-Failure: *=429
```

Expected response:

```json
{
  "detail": "all providers unavailable"
}
```

with HTTP status:

```text
503 Service Unavailable
```

The failed request is not saved to conversation history.

---

# Automated Tests

The backend includes automated tests covering:

- Health endpoint
- Empty-message validation
- Maximum message-length validation
- Successful chat requests
- Conversation history
- Unknown session handling
- All-provider failure
- Failed-request non-persistence
- Cache metadata
- Simulated provider failover

Run the tests:

```bash
cd backend
pytest -v
```

Current test result:

```text
10 passed
```

---

# Frontend Testing Contract

Important UI elements expose stable `data-testid` attributes.

```text
chat-input
send-button
assistant-message
meta-source
meta-model
meta-latency
meta-input-tokens
meta-output-tokens
system-prompt-input
```

These allow automated UI testing without relying on CSS classes or visible text.

---

# Technology Stack

## Backend

- Python 3.10
- FastAPI
- LiteLLM
- SQLite
- Uvicorn
- Pytest

## Frontend

- React
- Vite
- JavaScript
- CSS
- Nginx

## Infrastructure

- Docker
- Docker Compose
- Git
- GitHub

## LLM Providers

- Google Gemini
- Groq

---

# Deployment

## Frontend

```text
TODO: Add deployed frontend URL
```

## Backend

```text
TODO: Add deployed backend URL
```

Production CORS will be configured to allow the deployed frontend origin.

---

# Demo Video

```text
TODO: Add 2-3 minute demo video URL
```

The demo video will show:

1. Multi-turn conversation
2. Response metadata
3. Automatic provider failover
4. LiteLLM cache hit
5. Token usage
6. Dockerized local execution

---

# Security

RelayAI follows several basic security practices:

- API keys are loaded from environment variables.
- Real `.env` files are excluded from Git.
- `.env.example` contains placeholder credentials only.
- API keys are never returned to the frontend.
- Failed LLM requests are not persisted.
- Production CORS is restricted to the deployed frontend origin.

---

# Author

**Himanshu Singh**

GitHub: [Himanshusingh94](https://github.com/Himanshusingh94)