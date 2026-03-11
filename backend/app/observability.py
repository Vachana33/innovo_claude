"""
Phase 1 observability utilities: request ID propagation and OpenAI call logging.

Provides:
- get_request_id() / set_request_id() — ContextVar-based request ID that propagates
  from async middleware into synchronous route helpers via anyio thread context copying.
- log_openai_call() — context manager to log every OpenAI/Whisper call with timing
  and token usage, and emit a structured PostHog event. Named "openai_call" to cover
  both chat completions and audio transcription.

PostHog user attribution in log_openai_call:
  Callers may set ctx["user_email"], ctx["company_id"], ctx["document_id"] inside the
  with-block. These are forwarded to PostHog if present. When not set (e.g. in helper
  functions without user context), the PostHog distinct_id falls back to "backend".
"""
import os
import time
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Generator

# Context variable to carry request_id across async/sync boundaries.
# FastAPI uses anyio.to_thread.run_sync which copies the calling context into the
# thread, so this propagates automatically into synchronous route helpers.
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Return the request ID for the current request context, or None."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> object:
    """
    Set the request ID for the current context.
    Returns the token produced by ContextVar.set() so the caller can reset it.
    """
    return _request_id_var.set(request_id)


def reset_request_id(token: object) -> None:
    """Reset the request ID context variable using the token from set_request_id()."""
    _request_id_var.reset(token)  # type: ignore[arg-type]


# Per-token pricing in USD for known models.
# Add new models here as they are introduced. Models not listed return cost=None.
_MODEL_PRICING: dict = {
    "gpt-4o-mini": {
        "prompt": 0.00000015,       # $0.15 per 1M prompt tokens
        "completion": 0.0000006,    # $0.60 per 1M completion tokens
    },
}


def _compute_cost(
    model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
) -> Optional[float]:
    """
    Compute estimated USD cost for a single OpenAI call.

    Returns None if the model is not in the pricing table or either
    token count is unavailable (e.g. Whisper audio transcription).
    """
    pricing = _MODEL_PRICING.get(model)
    if pricing is None or prompt_tokens is None or completion_tokens is None:
        return None
    cost = prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]
    return round(cost, 6)


@contextmanager
def log_openai_call(
    logger: logging.Logger,
    function_name: str,
    file_path: str,
    model: str,
) -> Generator[dict, None, None]:
    """
    Context manager to log an OpenAI API call (chat completions or audio transcription)
    with timing and token usage, and emit a PostHog 'llm_call' event.

    Usage:
        with log_openai_call(logger, "my_function", __file__, "gpt-4o-mini") as ctx:
            response = client.chat.completions.create(...)
            ctx["response"] = response
            # Optional: add user context for PostHog attribution
            ctx["user_email"] = current_user.email   # if available
            ctx["company_id"] = company.id            # if available
            ctx["document_id"] = document.id          # if available

    On success, logs (INFO):
        openai_call | file=... function=... model=... duration_ms=...
                      prompt_tokens=... completion_tokens=... total_tokens=...
                      success=true request_id=...

    On failure, logs (ERROR) with full stack trace:
        openai_call_failed | file=... function=... model=... duration_ms=...
                             success=false request_id=...

    Note: Whisper transcription responses do not include usage data;
    token fields will log as None in that case — this is expected.
    """
    # Import here to avoid any circular import risk at module load time
    from app.posthog_client import capture_event  # noqa: PLC0415

    ctx: dict = {}
    start = time.monotonic()
    request_id = get_request_id()
    short_file = os.path.basename(file_path)

    try:
        yield ctx
        duration_ms = int((time.monotonic() - start) * 1000)
        response = ctx.get("response")
        usage = getattr(response, "usage", None) if response else None
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        total_tokens = getattr(usage, "total_tokens", None) if usage else None

        logger.info(
            "openai_call | file=%s function=%s model=%s duration_ms=%d "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s "
            "success=true request_id=%s",
            short_file,
            function_name,
            model,
            duration_ms,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            request_id or "none",
        )

        capture_event(
            distinct_id=ctx.get("user_email") or "backend",
            event="llm_call",
            properties={
                "request_id": request_id or "none",
                "file": short_file,
                "function_name": function_name,
                "model": model,
                "duration_ms": duration_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": _compute_cost(model, prompt_tokens, completion_tokens),
                "success": True,
                "company_id": ctx.get("company_id"),
                "document_id": ctx.get("document_id"),
            },
        )

    except Exception:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "openai_call_failed | file=%s function=%s model=%s duration_ms=%d "
            "success=false request_id=%s",
            short_file,
            function_name,
            model,
            duration_ms,
            request_id or "none",
            exc_info=True,
        )

        capture_event(
            distinct_id=ctx.get("user_email") or "backend",
            event="llm_call",
            properties={
                "request_id": request_id or "none",
                "file": short_file,
                "function_name": function_name,
                "model": model,
                "duration_ms": duration_ms,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": None,
                "success": False,
                "company_id": ctx.get("company_id"),
                "document_id": ctx.get("document_id"),
            },
        )

        raise
