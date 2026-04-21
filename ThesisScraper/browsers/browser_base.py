import os
import time
import random
import logging
import functools
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, Any

from patchright.sync_api import (
    sync_playwright,
    Page,
    BrowserContext,
    TimeoutError as PWTimeoutError,
)
from .utils import HumanTypist

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SelectorError(RuntimeError):
    """Raised when no fallback selector resolves for a given key."""


class SessionError(RuntimeError):
    """Raised when the browser session is unhealthy and cannot be recovered."""


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def _retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """Decorator: retry a method on failure with exponential backoff."""
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
                            "%s failed after %d attempts: %s",
                            fn.__name__, attempts, exc,
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


# ---------------------------------------------------------------------------
# Base browser
# ---------------------------------------------------------------------------

class BaseBrowser(ABC):
    """
    Base class for all AI-platform scrapers.

    Subclasses define platform-specific constants and CSS selector registries.
    Common logic — browser lifecycle, selector resolution, retry-wrapped
    interactions, data extraction — lives here.

    Subclass checklist (must set / may override):

        _HOME_URL               URL for a new chat
        _LOGIN_URL              URL shown on startup for manual login
        _SESSION_DIR            folder name for persistent browser data
        SELECTOR_CANDIDATES     dict[str, list[str]] — ordered CSS fallbacks
        get_active_model()      abstract — read current model from the UI
    """

    # -- Subclass MUST set these -----------------------------------------------
    _HOME_URL: str
    _LOGIN_URL: str
    _SESSION_DIR: str
    SELECTOR_CANDIDATES: Dict[str, List[str]]

    # -- Subclass MAY override these -------------------------------------------
    _PLATFORM_NAME: str = "Unknown"
    _WINDOW_WIDTH: int = 500
    _WINDOW_HEIGHT: int = 700
    _AUTH_URL_MARKERS: tuple = ("login", "signin", "auth")
    _STRIP_SELECTORS: str = "button, [role='button'], [aria-hidden='true']"
    _RESPONSE_FALLBACK_KEY: str = "send_button"

    DEFAULT_TIMEOUTS: Dict[str, int] = {
        "page_load":          30_000,
        "response_start":      5_000,
        "response_complete":  180_000,
        "response_fallback":   15_000,
        "selector_probe":      2_000,
    }

    # -- Lifecycle -------------------------------------------------------------

    def __init__(
        self,
        headless: bool = False,
        timeouts: Optional[Dict[str, int]] = None,
    ):
        self.SELECTORS: Dict[str, str] = {}
        self.user_data_dir = os.path.join(os.getcwd(), self._SESSION_DIR)
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.timeouts = {**self.DEFAULT_TIMEOUTS, **(timeouts or {})}
        self._launch_browser(headless)
        self.page.goto(self._LOGIN_URL)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _launch_browser(self, headless: bool):
        """Start Playwright and open a persistent Chromium context."""
        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=headless,
            viewport={"width": self._WINDOW_WIDTH, "height": self._WINDOW_HEIGHT},
            args=[
                f"--window-size={self._WINDOW_WIDTH},{self._WINDOW_HEIGHT}",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self.page = (
            self.context.pages[0] if self.context.pages else self.context.new_page()
        )

    def close(self):
        """Shut down the browser and Playwright instance."""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()

    # -- Selector resolution ---------------------------------------------------

    def _selector(self, key: str) -> str:
        """Return the first working selector for *key*, caching the result."""
        if key in self.SELECTORS:
            return self.SELECTORS[key]

        candidates = self.SELECTOR_CANDIDATES.get(key, [])
        for candidate in candidates:
            try:
                self.page.wait_for_selector(
                    candidate, timeout=self.timeouts["selector_probe"]
                )
                logger.debug("Selector resolved for '%s': %s", key, candidate)
                self.SELECTORS[key] = candidate
                return candidate
            except PWTimeoutError:
                continue

        raise SelectorError(
            f"No working selector for '{key}'. Tried: {candidates}. "
            f"The {self._PLATFORM_NAME} UI may have changed — "
            f"update SELECTOR_CANDIDATES['{key}']."
        )

    def validate_selectors(self) -> Dict[str, Optional[str]]:
        """Probe every registered selector; return key -> resolved or None."""
        report = {}
        for key in self.SELECTOR_CANDIDATES:
            try:
                report[key] = self._selector(key)
            except SelectorError:
                logger.warning("Selector broken: '%s'", key)
                report[key] = None
        return report

    # -- Session health --------------------------------------------------------

    def is_session_healthy(self) -> bool:
        """True if the page is open, logged in, and the chat input is reachable."""
        try:
            if self.page.is_closed():
                return False
            if any(m in self.page.url for m in self._AUTH_URL_MARKERS):
                logger.warning("Session appears to be logged out.")
                return False
            self.page.wait_for_selector(
                self._selector("chat_input"),
                timeout=self.timeouts["selector_probe"],
            )
            return True
        except Exception:
            return False

    def recover_session(self):
        """Re-navigate home and verify health. Raises SessionError on failure."""
        logger.warning("Session unhealthy — attempting recovery…")
        try:
            self.SELECTORS.clear()
            self.navigate_home()
            if not self.is_session_healthy():
                raise SessionError("Post-recovery health check failed.")
            logger.info("Session recovered successfully.")
        except Exception as exc:
            raise SessionError(f"Session recovery failed: {exc}") from exc

    def _recover_page(self):
        """Re-acquire a valid page after a frame detachment."""
        self.SELECTORS.clear()
        open_pages = [p for p in self.context.pages if not p.is_closed()]
        self.page = open_pages[0] if open_pages else self.context.new_page()

    # -- Navigation & state ----------------------------------------------------

    @_retry(attempts=3, exceptions=(PWTimeoutError, SelectorError))
    def navigate_home(self):
        """Navigate to a new chat page and wait for the input to be ready."""
        try:
            self.page.goto(self._HOME_URL)
        except Exception as exc:
            if "Frame was detached" in str(exc):
                logger.warning("Frame detached — recovering page…")
                self._recover_page()
                self.page.goto(self._HOME_URL)
            elif "interrupted by another navigation" in str(exc):
                # Observed on Gemini (gemini.google.com/app), which performs a
                # client-side redirect during load that Playwright reports as
                # a second navigation interrupting the first. The page still
                # ends up at the right URL. The wait_for_selector below is the
                # real readiness gate, so it's safe to swallow this here.
                # If a future platform exhibits the same symptom, add it to
                # this comment rather than broadening the catch.
                logger.debug("Navigation interrupted by SPA redirect — proceeding.")
            else:
                raise
        self.page.wait_for_selector(
            self._selector("chat_input"), timeout=self.timeouts["page_load"]
        )
        self._post_navigate()

    def _post_navigate(self):
        """Hook called after navigate_home. Override for extra platform setup."""

    @abstractmethod
    def get_active_model(self) -> str:
        """Return the currently active model name as shown in the UI."""

    # -- Interaction -----------------------------------------------------------

    @_retry(attempts=3, exceptions=(PWTimeoutError, SelectorError))
    def send_message(self, text: str):
        """Type a message into the chat input and submit it."""
        chat_input = self.page.locator(self._selector("chat_input")).first
        chat_input.click()
        HumanTypist.type_text(chat_input, text)
        time.sleep(random.uniform(0.8, 1.2))
        self._submit_input()

    def _submit_input(self):
        """Submit the current input. Default: press Enter. Override if needed."""
        self.page.locator(self._selector("chat_input")).first.press("Enter")

    @_retry(attempts=2, exceptions=(PWTimeoutError,))
    def wait_for_response(self):
        """Block until the model finishes generating its response."""
        try:
            self.page.wait_for_selector(
                self._selector("stop_button"),
                timeout=self.timeouts["response_start"],
            )
            self.page.locator(self._selector("stop_button")).wait_for(
                state="detached", timeout=self.timeouts["response_complete"]
            )
            logger.info("Response received.")
        except Exception:
            logger.info(
                "Stop-button strategy failed — falling back to '%s'.",
                self._RESPONSE_FALLBACK_KEY,
            )
            self.page.wait_for_selector(
                self._selector(self._RESPONSE_FALLBACK_KEY),
                state="visible",
                timeout=self.timeouts["response_fallback"],
            )

    def rate_limit(self):
        """Sleep for a randomised duration to reduce bot-detection risk."""
        delay = random.randint(2, 7) + random.random()
        logger.info("Rate limiting: sleeping for %.2fs", delay)
        time.sleep(delay)

    # -- Data extraction -------------------------------------------------------

    @_retry(attempts=3, exceptions=(PWTimeoutError, SelectorError))
    def get_history(self) -> List[Dict]:
        """Scrape the full conversation history."""
        self.page.wait_for_selector(
            self._selector("response_node"), state="visible"
        )

        responses = self.page.locator(self._selector("response_node")).all()
        queries = self.page.locator(self._selector("user_query")).all()

        if len(responses) != len(queries):
            # Index-based pairing assumes one user query per response. If the
            # platform ever renders an unpaired node (e.g. a system notice or
            # a streaming partial), every subsequent turn is mis-aligned.
            logger.warning(
                "Turn-pairing mismatch: %d response nodes vs %d user queries. "
                "Output may be misaligned.",
                len(responses), len(queries),
            )

        history = []
        for i, resp in enumerate(responses):
            history.append({
                "turn": i + 1,
                "user": (
                    queries[i].inner_text().strip() if i < len(queries) else "N/A"
                ),
                "model_output": self._extract_response_text(resp),
            })
        return history

    def _extract_response_text(self, resp) -> str:
        """Extract response text, stripping UI chrome (buttons etc.) at the DOM level."""
        return resp.evaluate(
            """(el, sel) => {
                const clone = el.cloneNode(true);
                clone.querySelectorAll(sel).forEach(n => n.remove());
                return clone.innerText;
            }""",
            self._STRIP_SELECTORS,
        ).strip()
