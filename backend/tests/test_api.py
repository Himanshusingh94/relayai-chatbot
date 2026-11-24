import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(BACKEND_DIR))

os.environ["DATABASE_URL"] = "sqlite:///./test_app.db"


from fastapi.testclient import TestClient

import main
from database import init_db


init_db()

client = TestClient(main.app)

def fake_llm_result():
    return {
        "reply": "Mock AI response",
        "metadata": {
            "resolution_source": "LIVE_INFERENCE",
            "model": "test-model",
            "latency_ms": 25,
            "input_tokens": 10,
            "output_tokens": 5,
            "key_id": "key_1",
            "fallback_attempts": 0,
        },
    }


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["keys_configured"] >= 2
    assert data["cache_enabled"] is True


def test_chat_validation_empty_message():
    response = client.post(
        "/chat",
        json={
            "session_id": "validation-test",
            "message": "   ",
        },
    )

    assert response.status_code == 422


def test_chat_validation_long_message():
    response = client.post(
        "/chat",
        json={
            "session_id": "validation-test",
            "message": "a" * 4001,
        },
    )

    assert response.status_code == 422


def test_chat_success(monkeypatch):
    monkeypatch.setattr(
        main,
        "generate_reply",
        lambda messages,
        simulate_failure_header=None:
        fake_llm_result(),
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "success-test",
            "message": "Hello",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"] == "success-test"
    assert data["reply"] == "Mock AI response"

    metadata = data["metadata"]

    assert metadata["resolution_source"] == (
        "LIVE_INFERENCE"
    )
    assert metadata["input_tokens"] == 10
    assert metadata["output_tokens"] == 5
    assert metadata["key_id"] == "key_1"


def test_session_history(monkeypatch):
    monkeypatch.setattr(
        main,
        "generate_reply",
        lambda messages,
        simulate_failure_header=None:
        fake_llm_result(),
    )

    session_id = "history-test"

    chat_response = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "Remember this",
        },
    )

    assert chat_response.status_code == 200

    response = client.get(
        f"/sessions/{session_id}/messages"
    )

    assert response.status_code == 200

    messages = response.json()["messages"]

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Remember this"

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == (
        "Mock AI response"
    )


def test_unknown_session_returns_404():
    response = client.get(
        "/sessions/session-that-does-not-exist/messages"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "session not found"
    }


def test_all_providers_unavailable_not_saved(
    monkeypatch,
):
    def unavailable(
        messages,
        simulate_failure_header=None,
    ):
        raise RuntimeError(
            "all providers unavailable"
        )

    monkeypatch.setattr(
        main,
        "generate_reply",
        unavailable,
    )

    session_id = "failed-request-test"

    response = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "Do not save me",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "all providers unavailable"
    }

    history = client.get(
        f"/sessions/{session_id}/messages"
    )

    assert history.status_code == 404


def test_cache_metadata(monkeypatch):
    cached_result = {
        "reply": "Cached answer",
        "metadata": {
            "resolution_source": "LLM_CACHE",
            "model": "test-model",
            "latency_ms": 2,
            "input_tokens": 12,
            "output_tokens": 4,
            "key_id": None,
            "fallback_attempts": 0,
        },
    }

    monkeypatch.setattr(
        main,
        "generate_reply",
        lambda messages,
        simulate_failure_header=None:
        cached_result,
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "cache-metadata-test",
            "message": "Cached question",
        },
    )

    assert response.status_code == 200

    metadata = response.json()["metadata"]

    assert metadata["resolution_source"] == (
        "LLM_CACHE"
    )
    assert metadata["key_id"] is None
    assert metadata["fallback_attempts"] == 0
    assert metadata["input_tokens"] == 12
    assert metadata["output_tokens"] == 4

def test_simulated_key_1_failure_falls_back(
    monkeypatch,
):
    fallback_result = {
        "reply": "Fallback worked",
        "metadata": {
            "resolution_source": "LIVE_INFERENCE",
            "model": "groq/openai/gpt-oss-120b",
            "latency_ms": 100,
            "input_tokens": 15,
            "output_tokens": 6,
            "key_id": "key_2",
            "fallback_attempts": 1,
        },
    }

    def fake_generate(
        messages,
        simulate_failure_header=None,
    ):
        assert simulate_failure_header == "key_1=429"
        return fallback_result

    monkeypatch.setattr(
        main,
        "generate_reply",
        fake_generate,
    )

    response = client.post(
        "/chat",
        headers={
            "X-Simulate-Failure": "key_1=429"
        },
        json={
            "session_id": "failover-unit-test",
            "message": "Test fallback",
        },
    )

    assert response.status_code == 200

    metadata = response.json()["metadata"]

    assert metadata["key_id"] == "key_2"
    assert metadata["fallback_attempts"] == 1
    assert metadata["resolution_source"] == (
        "LIVE_INFERENCE"
    )


def test_simulated_all_keys_failure(
    monkeypatch,
):
    def fake_generate(
        messages,
        simulate_failure_header=None,
    ):
        assert simulate_failure_header == "*=429"

        raise RuntimeError(
            "all providers unavailable"
        )

    monkeypatch.setattr(
        main,
        "generate_reply",
        fake_generate,
    )

    session_id = "all-fail-unit-test"

    response = client.post(
        "/chat",
        headers={
            "X-Simulate-Failure": "*=429"
        },
        json={
            "session_id": session_id,
            "message": "This must fail",
        },
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "all providers unavailable"
    }

    history = client.get(
        f"/sessions/{session_id}/messages"
    )

    assert history.status_code == 404