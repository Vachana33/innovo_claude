"""PostHog analytics client for Innovo backend."""
import os
import socket
import logging
from typing import Optional

import posthog

logger = logging.getLogger(__name__)

POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "")
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
POSTHOG_DISABLED = os.getenv("POSTHOG_DISABLED", "false").lower() == "true"

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
APP_VERSION = os.getenv("APP_VERSION", "dev")

try:
    _HOST = socket.gethostname()
except Exception:
    _HOST = "unknown"

_BASE_PROPERTIES: dict = {
    "project": "innovo_claude",
    "service": "backend",
    "environment": ENVIRONMENT,
    "app_version": APP_VERSION,
    "host": _HOST,
}


def init_posthog() -> None:
    if POSTHOG_DISABLED or not POSTHOG_API_KEY:
        logger.info("PostHog analytics disabled (POSTHOG_DISABLED=true or no API key).")
        posthog.disabled = True
        return
    posthog.api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST
    logger.info("PostHog analytics initialized (host=%s)", POSTHOG_HOST)


def shutdown_posthog() -> None:
    if not POSTHOG_DISABLED and POSTHOG_API_KEY:
        posthog.flush()
        logger.info("PostHog events flushed.")


def capture_event(
    distinct_id: str,
    event: str,
    properties: Optional[dict] = None,
) -> None:
    if POSTHOG_DISABLED or not POSTHOG_API_KEY:
        return
    try:
        props = {**_BASE_PROPERTIES, **(properties or {})}
        posthog.capture(distinct_id=distinct_id, event=event, properties=props)
    except Exception as exc:
        logger.warning("PostHog capture failed for event '%s': %s", event, str(exc))
