import os
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from database import (
    get_connection,
    get_messages,
    init_db,
    save_message,
)
from llm_service import (
    generate_reply,
    get_configured_key_count,
    is_cache_enabled,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RelayAI Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: Optional[str] = None

    @field_validator("session_id", "message")
    @classmethod
    def validate_not_blank(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("must not be empty")

        return value


@app.get("/health")
def health():
    connection = get_connection()

    try:
        connection.execute("SELECT 1")
    finally:
        connection.close()

    return {
        "status": "ok",
        "keys_configured": get_configured_key_count(),
        "cache_enabled": is_cache_enabled(),
    }


@app.post("/chat")
def chat(
    request: ChatRequest,
    x_simulate_failure: Optional[str] = Header(
        default=None,
        alias="X-Simulate-Failure",
    ),
):
    history = get_messages(request.session_id)

    llm_messages = []

    if request.system_prompt:
        llm_messages.append(
            {
                "role": "system",
                "content": request.system_prompt,
            }
        )

    for message in history:
        llm_messages.append(
            {
                "role": message["role"],
                "content": message["content"],
            }
        )

    llm_messages.append(
        {
            "role": "user",
            "content": request.message,
        }
    )

    try:
        result = generate_reply(llm_messages,
    simulate_failure_header=x_simulate_failure,
)
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable",
        )

    save_message(
        session_id=request.session_id,
        role="user",
        content=request.message,
    )

    save_message(
        session_id=request.session_id,
        role="assistant",
        content=result["reply"],
        metadata=result["metadata"],
    )

    return {
        "session_id": request.session_id,
        "reply": result["reply"],
        "metadata": result["metadata"],
    }

@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    messages = get_messages(session_id)

    if not messages:
        raise HTTPException(
            status_code=404,
            detail="session not found",
        )

    return {
        "session_id": session_id,
        "messages": messages,
    }