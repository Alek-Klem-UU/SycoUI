import time
import logging
import functools
from abc import ABC, abstractmethod
from typing import List, Dict, Callable, Any

logger = logging.getLogger(__name__)



"""
Use ABC because:
If a new browser class forgets to implement, say, get_history(),
Python raises a TypeError at instantiation time rather than
crashing mid-run when the method is first called.
"""

class BaseBrowser(ABC):
    """
    Interface contract for all AI platform scrapers.

    Every browser subclass must implement the methods below.
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abstractmethod
    def navigate_home(self):
        """Navigate to the platform's chat page and wait for the input to be ready."""

    @abstractmethod
    def get_active_model(self) -> str:
        """Return the name of the currently active model as shown in the UI."""

    @abstractmethod
    def send_message(self, text: str):
        """Type *text* into the chat input and submit it."""

    @abstractmethod
    def wait_for_response(self):
        """Block until the model finishes generating its response."""

    @abstractmethod
    def rate_limit(self):
        """Sleep for a randomised duration to reduce bot-detection risk."""

    @abstractmethod
    def get_history(self) -> List[Dict]:
        """Scrape and return the full conversation history as a list of turn dicts."""

    @abstractmethod
    def close(self):
        """Shut down the browser and release all resources."""



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
