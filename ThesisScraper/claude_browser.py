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
# Selectors marked [CONFIRMED] have been verified against the live claude.ai
# DOM by real scrapers. Selectors marked [INFERRED] are best guesses based on
# Claude's known React/Tailwind structure — run validate_selectors() after
# login and update any that resolve to None.
#
# When Claude updates its UI, add the new selector at the front of the list.
# Old ones stay as fallbacks until confirmed dead, then get pruned.
# -----------------------------------------------------------------------------

SELECTOR_CANDIDATES: Dict[str, List[str]] = {
    "chat_input": [
        # [CONFIRMED] — verified by multiple claude.ai automation scripts
        "div.ProseMirror[contenteditable='true']",
        "div[contenteditable='true']",
        "[data-testid='chat-input']",
    ],
    "send_button": [
        # [INFERRED] — Claude renders a submit button in the composer footer
        "button[aria-label='Send Message']",
        "button[type='button'][aria-label*='Send']",
        "button[data-testid='send-button']",
    ],
    "stop_button": [
        # [INFERRED] — appears during streaming, disappears when done
        "button[aria-label='Stop Response']",
        "button[aria-label*='Stop']",
        "button[data-testid='stop-button']",
    ],
    "response_complete_signal": [
        # [CONFIRMED] — the Copy button reliably appears only after a response
        # finishes. This is the most robust completion signal for claude.ai.
        "button[aria-label='Copy response']",
        "button[aria-label*='Copy']",
        "button[data-testid='copy-response-button']",
    ],
    "model_pill": [
        # [INFERRED] — the model selector button in the composer header
        "button[data-testid='model-selector-dropdown']",
        "button[aria-haspopup='listbox']",
        "[data-testid='model-selector']",
    ],
  
    "user_query": [
        # [INFERRED] — each human turn container
        "div[data-testid='user-message']",
        ".font-user-message",
        "[class*='HumanMessage']",
    ],
    "think_button": [
        # [INFERRED] — extended thinking toggle, only present on thinking models
        "button[data-testid='thinking-toggle']",
        "button[aria-label*='thinking']",
        "button[aria-expanded][aria-label*='thought']",
    ],
    "thought_box": [
        # [INFERRED] — extended thinking content block
        "div[data-testid='thinking-block']",
        "[class*='thinking-content']",
        "[class*='ThinkingBlock']",
    ],
    "response_node": [
    # [CONFIRMED] — seen in live DOM snippet, Feb 2026
    "div.standard-markdown",
    "[class*='standard-markdown']",
    # Old fallbacks below — likely dead, prune once confirmed
    "div[data-testid='assistant-message']",
    ".font-claude-message",
    "[class*='AssistantMessage']",
    ],
    "message_body": [
        # [CONFIRMED] — response prose now uses font-claude-response-body
        ".font-claude-response-body",
        "div.standard-markdown",
        # Old fallbacks
        "div[data-testid='assistant-message'] .prose, "
        "div[data-testid='assistant-message'] [class*='prose'], "
        ".font-claude-message .prose",
        "div[data-testid='assistant-message']",
    ]
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


class ClaudeBrowser:
    _WINDOW_WIDTH  = 500
    _WINDOW_HEIGHT = 700
    _CLAUDE_URL    = "https://claude.ai/new"
    _CLAUDE_URL_LOGIN = "https://claude.ai/login"

    # Substrings that indicate the session has expired and Claude has
    # redirected to an authentication page.
    _AUTH_URL_MARKERS = ("login", "auth", "signin", "accounts.google")

    # Timeout configuration (milliseconds) — override per-instance via constructor
    DEFAULT_TIMEOUTS = {
        "page_load":          30_000,
        "response_start":      5_000,
        "response_complete":  180_000,
        "response_fallback":   15_000,  # used when stop button approach fails
        "selector_probe":      2_000,
    }

    def __init__(self, headless: bool = False, timeouts: Optional[Dict[str, int]] = None):
        self.SELECTORS: Dict[str, str] = {}  # instance-level — not shared across instances
        self.user_data_dir = os.path.join(os.getcwd(), "claude_ui_session")
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.timeouts = {**self.DEFAULT_TIMEOUTS, **(timeouts or {})}
        self._setup(headless)
        self.page.goto(self._CLAUDE_URL_LOGIN)

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
        Raises SelectorError if none match — add the new selector to
        SELECTOR_CANDIDATES[key] and it will be picked up automatically.
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
            f"Tried: {candidates}. The Claude UI may have changed — "
            f"update SELECTOR_CANDIDATES['{key}'] with the new selector."
        )

    def validate_selectors(self) -> Dict[str, Optional[str]]:
        """
        Probe all registered selectors and return a health report.

        Returns a dict of key → resolved selector, or None if broken.
        Call this right after login to surface any UI breakage early.
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
            # Detect silent redirects to the Anthropic/Google login page
            if any(marker in self.page.url for marker in self._AUTH_URL_MARKERS):
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
        """Navigate to Claude and wait for the input to be ready."""
        self.page.goto(self._CLAUDE_URL)
        self.page.wait_for_selector(
            self._selector("chat_input"), timeout=self.timeouts["page_load"]
        )

    def get_active_model(self) -> str:
        """Return the active model name (e.g. Claude Sonnet 4, Claude Opus 4)."""
        try:
            for pill in self.page.locator(self._selector("model_pill")).all():
                if pill.is_visible():
                    return pill.inner_text().strip().replace("\n", "")
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
        self.page.locator(self._selector("send_button")).click()

    @_retry(attempts=2, exceptions=(PWTimeoutError,))
    def wait_for_response(self):
        """
        Block until the model finishes generating its response.

        Primary strategy: watch the stop button appear then disappear.
        Fallback strategy: wait for the Copy button to appear, which is the
        most reliable confirmed signal that a response has fully completed.
        """
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
            # Fallback: the Copy button only appears after generation finishes.
            # This is more reliable than watching the send button.
            logger.info("Stop button strategy failed — falling back to Copy button signal.")
            self.page.wait_for_selector(
                self._selector("response_complete_signal"),
                state="visible",
                timeout=self.timeouts["response_fallback"],
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
        """Strip Claude UI chrome strings from extracted text."""
        for artifact in ("Show thinking", "Hide thinking", "Copy code", "Copy"):
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