"""PostHog analytics client for Innovo backend.

Initializes the PostHog Python SDK using environment variables and
exposes a shared client instance for use across the application.
"""

import os
import logging

import posthog

logger = logging.getLogger(__name__)

# Read configuration from environment
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "")
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
POSTHOG_DISABLED = os.getenv("POSTHOG_DISABLED", "false").lower() == "true"


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
