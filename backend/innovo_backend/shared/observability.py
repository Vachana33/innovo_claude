"""
Phase 1 observability utilities: request ID propagation and OpenAI call logging.
"""
import os
import time
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Generator

_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


def set_request_id(request_id: str) -> object:
    return _request_id_var.set(request_id)


def reset_request_id(token: object) -> None:
    _request_id_var.reset(token)  # type: ignore[arg-type]


_MODEL_PRICING: dict = {
    "gpt-4o-mini": {
        "prompt": 0.00000015,
        "completion": 0.0000006,
    },
}


def _compute_cost(
    model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
) -> Optional[float]:
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
    from innovo_backend.shared.posthog_client import capture_event  # noqa: PLC0415

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
            short_file, function_name, model, duration_ms,
            prompt_tokens, completion_tokens, total_tokens,
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
            short_file, function_name, model, duration_ms,
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
