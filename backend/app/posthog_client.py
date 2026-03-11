"""PostHog analytics client for Innovo backend.

Initializes the PostHog Python SDK using environment variables and
exposes a shared client instance for use across the application.
"""

import os
import socket
import logging
from typing import Optional

import posthog

logger = logging.getLogger(__name__)

# Read configuration from environment
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "")
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
POSTHOG_DISABLED = os.getenv("POSTHOG_DISABLED", "false").lower() == "true"

# Metadata attached to every event automatically
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
APP_VERSION = os.getenv("APP_VERSION", "dev")

# Resolved once at module load so every event gets a consistent host value
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
    """Initialize the PostHog client on application startup."""
    if POSTHOG_DISABLED or not POSTHOG_API_KEY:
        logger.info("PostHog analytics disabled (POSTHOG_DISABLED=true or no API key).")
        posthog.disabled = True
        return

    posthog.api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST
    logger.info("PostHog analytics initialized (host=%s)", POSTHOG_HOST)


def shutdown_posthog() -> None:
    """Flush pending PostHog events on application shutdown."""
    if not POSTHOG_DISABLED and POSTHOG_API_KEY:
        posthog.flush()
        logger.info("PostHog events flushed.")


def capture_event(
    distinct_id: str,
    event: str,
    properties: Optional[dict] = None,
) -> None:
    """
    Safely capture a PostHog event. Never raises.

    Automatically merges project/service/environment/app_version/host
    into every event so dashboards can filter by system identity.

    Skips silently if PostHog is disabled or the API key is absent.

    Args:
        distinct_id: User email, "backend", or any stable actor identifier.
        event: Event name (e.g. "llm_call", "document_created").
        properties: Optional dict of event-specific properties.
    """
    if POSTHOG_DISABLED or not POSTHOG_API_KEY:
        return
    try:
        props = {**_BASE_PROPERTIES, **(properties or {})}
        posthog.capture(
    distinct_id=distinct_id,
    event=event,
    properties=props
)
    except Exception as exc:
        logger.warning("PostHog capture failed for event '%s': %s", event, str(exc))
