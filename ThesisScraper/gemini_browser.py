import os
import time
import random
import logging
import functools
from typing import List, Dict, Optional, Callable, Any

from patchright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PWTimeoutError
from utils import HumanTypist

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Selector Registry
#
# Each key maps to an ordered list of fallback selectors. The scraper tries
# them left-to-right and uses the first one that matches. When Gemini updates
# its UI, add the new selector at the front of the list — old ones stay as
# fallbacks until confirmed dead, then get pruned.
# -----------------------------------------------------------------------------

SELECTOR_CANDIDATES: Dict[str, List[str]] = {
    "chat_input": [
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
        "rich-textarea div[contenteditable]",
    ],
    "send_button": [
        "button[aria-label*='Send message']",
        "button[aria-label*='Send']",
        "button[data-test-id='send-button']",
    ],
    "stop_button": [
        "button[aria-label*='Stop generating']",
        "button[aria-label*='Stop']",
        "button[data-test-id='stop-button']",
    ],
    "mic_button": [
        "button[name='Use microphone']",
        "button[aria-label*='microphone']",
    ],
    "model_pill": [
        "[data-test-id='logo-pill-label-container']",
        "[data-test-id='model-selector']",
        ".model-pill-label",
    ],
    "response_node": [
        "model-response",
        "[data-test-id='model-response']",
        ".model-response",
    ],
    "user_query": [
        "user-query",
        "[data-test-id='user-query']",
        ".user-query",
    ],
    "think_button": [
        "div.thoughts-header-button-content",
        "button.thoughts-toggle",
        "[data-test-id='thoughts-toggle']",
    ],
    "thought_box": [
        "[class*='thoughts-content']",
        "[data-test-id='thoughts-content']",
        ".thought-content",
    ],
    "message_body": [
        ".message-content, .markdown, response-body",  # kept as a single multi-selector
        "[data-test-id='response-body']",
    ],
}


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


class GeminiBrowser:
    _WINDOW_WIDTH  = 500
    _WINDOW_HEIGHT = 700
    _GEMINI_URL    = "https://gemini.google.com/app"

    # Timeout configuration (milliseconds) — override per-instance via constructor
    DEFAULT_TIMEOUTS = {
        "page_load":         30_000,
        "response_start":     5_000,
        "response_complete": 180_000,
        "mic_fallback":      15_000,
        "selector_probe":     2_000,
    }

    def __init__(self, headless: bool = False, timeouts: Optional[Dict[str, int]] = None):
        self.SELECTORS: Dict[str, str] = {}  # instance-level cache — not shared across instances
        self.user_data_dir = os.path.join(os.getcwd(), "gemini_ui_session")
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.timeouts = {**self.DEFAULT_TIMEOUTS, **(timeouts or {})}
        self._setup(headless)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -------------------------------------------------------------------------
    # Setup
    # -------------------------------------------------------------------------

    def _setup(self, headless: bool):
        """Initialize the browser with stealth settings."""
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
        # Safely acquire the first page or open a new one if none exist
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    # -------------------------------------------------------------------------
    # Selector Resolution
    # -------------------------------------------------------------------------

    def _selector(self, key: str) -> str:
        """
        Return the first working selector for *key*, caching the result.

        Tries each candidate in SELECTOR_CANDIDATES[key] against the live page.
        Raises SelectorError if none match, which signals that the UI has changed
        in a way that requires a new fallback to be added.
        """
        if key in self.SELECTORS:
            return self.SELECTORS[key]

        candidates = SELECTOR_CANDIDATES.get(key, [])
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
            f"No working selector found for '{key}'. "
            f"Tried: {candidates}. The Gemini UI may have changed — "
            f"update SELECTOR_CANDIDATES['{key}'] with the new selector."
        )

    def validate_selectors(self) -> Dict[str, Optional[str]]:
        """
        Probe all registered selectors and return a health report.

        Returns a dict mapping each key to its resolved selector, or None if
        it could not be resolved. Useful for catching breakage early.
        """
        report = {}
        for key in SELECTOR_CANDIDATES:
            try:
                report[key] = self._selector(key)
            except SelectorError:
                logger.warning("Selector broken: '%s'", key)
                report[key] = None
        return report

    # -------------------------------------------------------------------------
    # Session Health
    # -------------------------------------------------------------------------

    def is_session_healthy(self) -> bool:
        """Return True if the page is open, logged in, and the chat input is reachable."""
        try:
            if self.page.is_closed():
                return False
            # Detect silent redirects to the Google login page
            if "signin" in self.page.url or "accounts.google" in self.page.url:
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
        """
        Attempt to recover from a broken session by re-navigating home.

        Raises SessionError if recovery fails.
        """
        logger.warning("Session unhealthy — attempting recovery…")
        try:
            self.SELECTORS.clear()  # Bust selector cache; UI may have changed
            self.navigate_home()
            if not self.is_session_healthy():
                raise SessionError("Post-recovery health check failed.")
            logger.info("Session recovered successfully.")
        except Exception as exc:
            raise SessionError(f"Session recovery failed: {exc}") from exc

    # -------------------------------------------------------------------------
    # Navigation & State
    # -------------------------------------------------------------------------

    @_retry(attempts=3, exceptions=(PWTimeoutError, SelectorError))
    def navigate_home(self):
        """Navigate to the Gemini app and wait for the input to be ready."""
        self.page.goto(self._GEMINI_URL)
        self.page.wait_for_selector(
            self._selector("chat_input"), timeout=self.timeouts["page_load"]
        )

    def get_active_model(self) -> str:
        """Return the active model name (e.g. Snel, Pro, or Thinking)."""
        try:
            for pill in self.page.locator(self._selector("model_pill")).all():
                if pill.is_visible():
                    raw = pill.inner_text().split("\n")[0]
                    return raw.replace("keyboard_arrow_down", "").strip()
        except Exception as e:
            logger.error("Mode detection failed: %s", e)
        return "Unknown"

    # -------------------------------------------------------------------------
    # Interaction
    # -------------------------------------------------------------------------

    @_retry(attempts=3, exceptions=(PWTimeoutError, SelectorError))
    def send_message(self, text: str, auto_enter: bool = False):
        """Type a message into the chat input and send it."""
        chat_input = self.page.locator(self._selector("chat_input")).first
        chat_input.click()
        HumanTypist.type_text(chat_input, text)
        time.sleep(random.uniform(0.8, 1.2))

        
        chat_input.press("Enter")
       

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
            # Fallback: wait for the mic button to reappear
            self.page.wait_for_selector(
                self._selector("mic_button"),
                state="visible",
                timeout=self.timeouts["mic_fallback"],
            )

    def rate_limit(self):
        """Sleep for a randomized duration to reduce bot-detection risk."""
        delay = random.randint(2, 7) + random.random()
        logger.info("Rate limiting: sleeping for %.2fs", delay)
        time.sleep(delay)

    # -------------------------------------------------------------------------
    # Data Extraction
    # -------------------------------------------------------------------------

    @_retry(attempts=3, exceptions=(PWTimeoutError, SelectorError))
    def get_history(self) -> List[Dict]:
        """
        Scrape the full conversation history.

        Each entry contains the turn number, user message, optional thinking
        block, and the final model output.
        """
        self.page.wait_for_selector(
            self._selector("response_node"), state="visible"
        )

        responses = self.page.locator(self._selector("response_node")).all()
        queries   = self.page.locator(self._selector("user_query")).all()

        history = []
        for i, resp in enumerate(responses):
         
            full_text  = self._get_text_safe(resp.locator(self._selector("message_body")).last)
            
            history.append({
                "turn":         i + 1,
                "user":         queries[i].inner_text().strip() if i < len(queries) else "N/A",
                "model_output": self._clean_ui_artifacts(full_text),
            })

        return history

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------


    def _get_text_safe(self, locator) -> str:
        """Return inner text of the first match, or an empty string if none."""
        return locator.first.inner_text().strip() if locator.count() > 0 else ""

    def _clean_ui_artifacts(self, text: str) -> str:
        """Strip Gemini UI chrome strings from extracted text."""
        for artifact in ("Show thinking", "Hide thinking"):
            text = text.replace(artifact, "")
        return text.strip()

    # -------------------------------------------------------------------------
    # Teardown
    # -------------------------------------------------------------------------

    def close(self):
        """Shut down the browser and Playwright instance."""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()