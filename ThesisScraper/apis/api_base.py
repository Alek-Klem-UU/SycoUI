import time
import random
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class APIError(RuntimeError):
    """Raised for unrecoverable API failures."""


# ---------------------------------------------------------------------------
# Base API client
# ---------------------------------------------------------------------------

class BaseAPI(ABC):
    """
    Base class for direct-API scrapers.

    Mirrors the public surface of `browsers.BaseBrowser` so that the run loop
    in main.py can treat API and Browser backends interchangeably:

        navigate_home()        no-op (no page state to reset)
        rate_limit()           short randomised sleep between requests
        get_active_model()     returns the configured model — trusted
        send_message(text)     issues the API call, stores the reply
        wait_for_response()    no-op (synchronous)
        get_history()          returns the single-turn conversation

    Each prompt is issued in an isolated request, matching the browser
    behaviour of opening a new chat per prompt — there is no shared state
    between prompts in the dataset.
    """

    # -- Subclass MUST set these -----------------------------------------------
    _MODEL_ID: str        # the actual API model identifier (e.g. "gpt-4o")
    _DISPLAY_MODE: str    # what get_active_model() reports — must match _MODE_MAP
    _PLATFORM_NAME: str = "Unknown"

    # Exception types this provider raises that should trigger a retry.
    # Subclasses override with provider-specific transient errors.
    _RETRY_EXCEPTIONS: tuple = (Exception,)

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError(f"{self._PLATFORM_NAME}: api_key is required.")
        self._api_key = api_key
        self._client = self._make_client()
        self._last_prompt: Optional[str] = None
        self._last_response: Optional[str] = None
        logger.info("Initialised %s API client (model: %s)",
                    self._PLATFORM_NAME, self._MODEL_ID)

    # -- Context manager (browser parity) --------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """No persistent resources to clean up by default."""

    # -- Subclass hooks --------------------------------------------------------

    @abstractmethod
    def _make_client(self):
        """Construct and return the provider SDK client."""

    @abstractmethod
    def _send(self, text: str) -> str:
        """Issue a single-turn request and return the response text."""

    # -- Browser-compatible interface ------------------------------------------

    def navigate_home(self):
        """No-op: API has no page state to reset between prompts."""

    def rate_limit(self):
        """Short jittered sleep so we don't hammer the provider."""
        delay = random.uniform(0.5, 1.5)
        logger.info("Rate limiting: sleeping for %.2fs", delay)
        time.sleep(delay)

    def get_active_model(self) -> str:
        """Return the configured display name. Always trusted for API mode."""
        return self._DISPLAY_MODE

    def wait_for_response(self):
        """No-op: send_message is synchronous."""

    def send_message(self, text: str):
        self._last_prompt = text
        self._last_response = self._send_with_retry(text)
        logger.info("Response received.")

    def _send_with_retry(
        self,
        text: str,
        attempts: int = 3,
        delay: float = 2.0,
        backoff: float = 2.0,
    ) -> str:
        """
        Inline retry loop that honours the subclass's _RETRY_EXCEPTIONS.

        The class-level _retry decorator can't be used here because it
        captures `exceptions` at decoration time, before the SDK is even
        imported — so a non-retriable APIError would be retried 3× anyway.
        Doing the loop inline lets us check the live tuple per call.
        """
        wait = delay
        for attempt in range(1, attempts + 1):
            try:
                return self._send(text)
            except self._RETRY_EXCEPTIONS as exc:
                if attempt == attempts:
                    logger.error(
                        "%s API call failed after %d attempts: %s",
                        self._PLATFORM_NAME, attempts, exc,
                    )
                    raise APIError(
                        f"{self._PLATFORM_NAME} API call failed after "
                        f"{attempts} attempts: {exc}"
                    ) from exc
                logger.warning(
                    "%s API call attempt %d/%d failed (%s). Retrying in %.1fs…",
                    self._PLATFORM_NAME, attempt, attempts, exc, wait,
                )
                time.sleep(wait)
                wait *= backoff
            except Exception as exc:
                # Non-retriable provider error — surface immediately, no retry.
                raise APIError(
                    f"{self._PLATFORM_NAME} API call failed: {exc}"
                ) from exc

    def get_history(self) -> List[Dict]:
        """Return the most recent single-turn exchange in browser-history shape."""
        if self._last_prompt is None or self._last_response is None:
            return []
        return [{
            "turn": 1,
            "user": self._last_prompt,
            "model_output": self._last_response,
        }]
