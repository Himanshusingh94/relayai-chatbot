import os
import time

import litellm
from litellm import Cache
from dotenv import load_dotenv

load_dotenv()
litellm.cache = Cache(type="local")


PROVIDERS = [
    {
        "key_id": "key_1",
        "model": os.getenv(
            "GEMINI_MODEL",
            "gemini/gemini-3.8-flash",
        ),
        "api_key": os.getenv("GEMINI_API_KEY"),
    },
    {
        "key_id": "key_2",
        "model": os.getenv(
            "GROQ_MODEL",
            "groq/openai/gpt-oss-120b",
        ),
        "api_key": os.getenv("GROQ_API_KEY"),
    },
]

def get_configured_key_count():
    return sum(
        1
        for provider in PROVIDERS
        if provider.get("api_key")
    )


def is_cache_enabled():
    return litellm.cache is not None

FAILURE_SIMULATION_ENABLED = (
    os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower()
    == "true"
)


def parse_simulated_failures(header_value):
    failures = {}

    if not FAILURE_SIMULATION_ENABLED:
        return failures

    if not header_value:
        return failures

    allowed_statuses = {429, 500, 502, 503}

    for item in header_value.split(","):
        item = item.strip()

        if "=" not in item:
            continue

        key_id, status_text = item.split("=", 1)

        key_id = key_id.strip()
        status_text = status_text.strip()

        try:
            status = int(status_text)
        except ValueError:
            continue

        if status in allowed_statuses:
            failures[key_id] = status

    return failures


def is_retryable_error(error):
    status_code = getattr(error, "status_code", None)

    if status_code in {429, 500, 502, 503}:
        return True

    error_text = str(error).lower()

    retryable_words = [
        "rate limit",
        "rate_limit",
        "quota",
        "429",
        "500",
        "502",
        "503",
        "service unavailable",
    ]

    return any(
        word in error_text
        for word in retryable_words
    )


def generate_reply(
    messages,
    simulate_failure_header=None,
):
    simulated_failures = parse_simulated_failures(
        simulate_failure_header
    )

    fallback_attempts = 0
    last_error = None

    for provider in PROVIDERS:
        if not provider["api_key"]:
            continue

        key_id = provider["key_id"]

        simulated_status = (
            simulated_failures.get(key_id)
            or simulated_failures.get("*")
        )

        if simulated_status:
            fallback_attempts += 1
            last_error = RuntimeError(
                f"simulated provider failure "
                f"{key_id}={simulated_status}"
            )
            continue

        start_time = time.perf_counter()

        try:
            response = litellm.completion(
                model=provider["model"],
                messages=messages,
                api_key=provider["api_key"],
            )
            hidden_params = getattr(
                response,
                "_hidden_params",
                {},
            ) or {}

            cache_hit = bool(
                hidden_params.get("cache_hit", False)
            )

            latency_ms = int(
                (time.perf_counter() - start_time)
                * 1000
            )

            reply = response.choices[0].message.content

            usage = getattr(response, "usage", None)

            input_tokens = 0
            output_tokens = 0

            if usage:
                input_tokens = (
                    getattr(
                        usage,
                        "prompt_tokens",
                        0,
                    )
                    or 0
                )

                output_tokens = (
                    getattr(
                        usage,
                        "completion_tokens",
                        0,
                    )
                    or 0
                )

            return {
                "reply": reply,
                "metadata": {
                    "resolution_source": (
                        "LLM_CACHE"
                        if cache_hit
                        else "LIVE_INFERENCE"
                    ),
                    "model": provider["model"],
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "key_id": (
                        None
                        if cache_hit
                        else key_id
                    ),
                    "fallback_attempts": (
                        0
                        if cache_hit
                        else fallback_attempts
                    ),
                },
            }

        except Exception as error:
            last_error = error

            if is_retryable_error(error):
                fallback_attempts += 1
                continue

            raise

    raise RuntimeError(
        "all providers unavailable"
    ) from last_error