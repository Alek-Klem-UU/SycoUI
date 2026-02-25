"""
browser_base.py — Shared infrastructure for all AI browser scrapers.

This module centralises code that is identical across every browser
implementation so it only needs to be maintained in one place:

  - _retry      : exponential-backoff decorator for flaky network calls
  - SelectorError: raised when no fallback CSS selector resolves
  - SessionError : raised when a browser session cannot be recovered
"""

import time
import logging
import functools
from typing import Callable, Any

logger = logging.getLogger(__name__)


class SelectorError(RuntimeError):
    """Raised when no fallback selector resolves for a given key."""


class SessionError(RuntimeError):
    """Raised when the browser session is unhealthy and cannot be recovered."""


def _retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Decorator: retry a method on failure with exponential backoff.

    Args:
        attempts:   Maximum number of tries.
        delay:      Initial wait between retries (seconds).
        backoff:    Multiplier applied to delay after each failure.
        exceptions: Exception types that trigger a retry.

    Why exponential backoff?
        Transient failures (network hiccups, slow page loads) are usually
        self-resolving. A fixed delay would waste time on long faults;
        an ever-growing delay avoids hammering a struggling server.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            wait = delay
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts:
                        logger.error(
                            "%s failed after %d attempts: %s", fn.__name__, attempts, exc
                        )
                        raise
                    logger.warning(
                        "%s attempt %d/%d failed (%s). Retrying in %.1fs…",
                        fn.__name__, attempt, attempts, exc, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator
