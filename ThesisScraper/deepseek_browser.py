import os
import time
import random
import logging
from typing import List, Dict, Optional

from patchright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PWTimeoutError
from utils import HumanTypist
from browser_base import BaseBrowser, _retry, SelectorError, SessionError

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Selector Registry
#
# Each key maps to an ordered list of fallback selectors. The scraper tries
# them left-to-right and uses the first one that matches. When DeepSeek updates
# its UI, add the new selector at the front of the list — old ones stay as
# fallbacks until confirmed dead, then get pruned.
# -----------------------------------------------------------------------------

SELECTOR_CANDIDATES: Dict[str, List[str]] = {
    "chat_input": [
        "textarea[placeholder*='DeepSeek']",       # matches any language ("Message DeepSeek", "Bericht DeepSeek", etc.)
        "textarea[placeholder*='Message']",
        "textarea.ds-scroll-area",                 # stable utility class, unlikely to be renamed
        "textarea#chat-input",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
    ],
    "send_button": [
        "button[aria-label*='Send message']",
        "button[aria-label*='Send']",
        "div[role='button'][aria-label*='Send']",
        "button[data-testid='send-button']",
    ],
    "stop_button": [
        "[role='button'].ds-icon-button svg path[d^='M2 4.88']",  # targets the specific stop square SVG path
        "[role='button'].ds-icon-button--l:not([aria-disabled='true'])",
        "div.ds-icon-button[role='button'][aria-disabled='false']",
        "button[aria-label*='Stop']",                             # kept as last-resort fallback
        "button[data-testid='stop-button']",
    ],
    "mic_button": [
        "button[aria-label*='microphone']",
        "button[aria-label*='voice']",
        "button[class*='voice']",
        "button[class*='mic']",
        "button[data-testid='mic-button']",
    ],
    "user_query": [
        "div.ds-message div.fbb737a4",             # confirmed ✓ — most specific
        "div.ds-message > div:first-child",        # structural fallback if fbb737a4 gets rehashed
        "div[class*='ds-message'] > div",          # broader ds- design system fallback
        "div[class*='message--user']",
        "div[class*='chat-message--user']",
        "div[data-testid='user-query']",
    ],
    "think_button": [
        "div[class*='thinking-toggle']",
        "button[class*='thinking-toggle']",
        "div[class*='think-header']",
        "span[class*='toggle-thinking']",
    ],
    "thought_box": [
        "div[class*='thinking-content']",
        "div[class*='thought-content']",
        "div[data-testid='thinking-block']",
        "div[class*='reasoningContent']",
    ],
    "response_node": [
        "div.ds-markdown",                          # confirmed ✓
        "div[class*='ds-markdown']",               # catches subclasses like ds-markdown--dense
        "div[data-testid='model-response']",
        "div[class*='message--assistant']",
    ],
    "message_body": [
        "div.ds-markdown",                          # confirmed ✓ — response IS the markdown div
        "div[class*='ds-markdown']",
        "div[class*='message-content']",
        "div[data-testid='response-body']",
    ],
    "search_toggle": [
        "div.ds-toggle-button:has-text('Zoeken')",         # Dutch web search ✓
        "div.ds-toggle-button:has-text('Search')",         # English fallback
        "[class*='ds-toggle-button']:has-text('Zoeken')",  # broader fallback
    ],
}



class DeepSeekBrowser(BaseBrowser):
    _WINDOW_WIDTH  = 500
    _WINDOW_HEIGHT = 700
    _DEEPSEEK_URL  = "https://chat.deepseek.com"

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
        self.user_data_dir = os.path.join(os.getcwd(), "deepseek_ui_session")
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.timeouts = {**self.DEFAULT_TIMEOUTS, **(timeouts or {})}
        self._setup(headless)

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
            f"Tried: {candidates}. The DeepSeek UI may have changed — "
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
            # Detect silent redirects to the DeepSeek login page
            if "login" in self.page.url or "sign" in self.page.url:
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
        """Navigate to the DeepSeek chat app and wait for the input to be ready."""
        self.page.goto(self._DEEPSEEK_URL)
        self.page.wait_for_selector(
            self._selector("chat_input"), timeout=self.timeouts["page_load"]
        )
        time.sleep(2)
        self.disable_search()

    def disable_search(self):
        """
        Disable the Deep Search toggle if it is currently active.

        DeepSeek's web-search mode can alter model behaviour and inflate
        response times, so we turn it off before each run.
        """
        try:
            toggle = self.page.locator(self._selector("search_toggle")).first
           
            toggle.click()
                
            time.sleep(random.uniform(0.3, 0.6))
            
        except Exception as e:
            logger.warning("Could not disable Deep Search toggle: %s", e)

    def get_active_model(self) -> str:
        """DeepSeek does not expose a model selector in the UI; always 'Default'."""
        return "Default"

    # -------------------------------------------------------------------------
    # Interaction
    # -------------------------------------------------------------------------

    @_retry(attempts=3, exceptions=(PWTimeoutError, SelectorError))
    def send_message(self, text: str):
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
        self.page.wait_for_selector(
            self._selector("response_node"), state="visible"
        )

        responses = self.page.locator(self._selector("response_node")).all()
        queries   = self.page.locator(self._selector("user_query")).all()

        history = []
        for i, resp in enumerate(responses):
            # Remove hidden MathML nodes before extracting text, otherwise
            # KaTeX double-renders every formula (MathML + HTML = duplicate garbage)
            full_text = resp.evaluate("""el => {
                const clone = el.cloneNode(true);
                // Remove MathML (screen-reader duplicate of each formula)
                clone.querySelectorAll('.katex-mathml').forEach(n => n.remove());
                // Remove aria-hidden katex-html spans (visible render is in outer span)
                clone.querySelectorAll('[aria-hidden="true"]').forEach(n => n.remove());
                return clone.innerText;
            }""")

            history.append({
                "turn":         i + 1,
                "user":         queries[i].inner_text().strip() if i < len(queries) else "N/A",
                "model_output": self._clean_ui_artifacts(full_text.strip()),
            })

        return history

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _get_text_safe(self, locator) -> str:
        """Return inner text of the first match, or an empty string if none."""
        return locator.first.inner_text().strip() if locator.count() > 0 else ""

    def _clean_ui_artifacts(self, text: str) -> str:
        """Strip DeepSeek UI chrome strings from extracted text."""
        for artifact in ("Show thinking", "Hide thinking", "Expand", "Collapse"):
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