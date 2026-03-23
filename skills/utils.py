"""
Shared utility functions used across multiple agents.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    operation: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (Exception,),
) -> Any:
    """
    Run an async callable with exponential back-off retry.

    Args:
        operation:    Async callable (no arguments — use functools.partial if needed).
        max_attempts: Maximum number of attempts.
        base_delay:   Seconds to wait before the first retry (doubles each time).
        exceptions:   Exception types that trigger a retry.

    Returns:
        Result of the operation on success.

    Raises:
        The last exception raised after all attempts are exhausted.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return await operation()
        except exceptions as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                wait = base_delay * (2 ** attempt)
                logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.1fs …",
                    attempt + 1,
                    max_attempts,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)

    raise last_exc  # type: ignore[misc]


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def mask_sensitive(data: dict, keys: tuple = ("api_key", "password", "token", "secret")) -> dict:
    """
    Return a shallow copy of *data* with sensitive values replaced by '***'.
    Safe to log.
    """
    return {k: ("***" if any(s in k.lower() for s in keys) else v) for k, v in data.items()}


def truncate(text: str, max_len: int = 500) -> str:
    """Truncate *text* to *max_len* characters, appending '…' if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
