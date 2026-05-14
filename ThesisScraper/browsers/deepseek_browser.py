import logging
import time
from patchright.sync_api import TimeoutError as PWTimeoutError
from .browser_base import BaseBrowser

logger = logging.getLogger(__name__)


_SELECTORS = {
    "chat_input": [
        "textarea[placeholder='Message DeepSeek']",
        "textarea[name='search']",
        "textarea[placeholder*='Message']",
    ],
    "send_button": [
        # Enabled only after text is typed — ds-icon-button--disabled is removed
        "div.ds-icon-button--sizing-container[role='button']:not(.ds-icon-button--disabled)",
        "div.ds-icon-button[role='button']:not(.ds-icon-button--disabled)",
    ],
    "search_toggle": [
        # Active state: ds-toggle-button--selected is present when search is ON
        "div.ds-toggle-button--selected[role='button']",
        "div.ds-toggle-button--selected",
    ],
    "response_node": [
        "div.ds-markdown",
        "div[class*='ds-markdown']",
    ],
    "user_query": [
        "div.ds-message",
    ],
    "message_body": [
        "div.ds-markdown",
        "div[class*='ds-markdown']",
    ],
}


class DeepSeekBrowser(BaseBrowser):
    _HOME_URL      = "https://chat.deepseek.com/"
    _LOGIN_URL     = "https://chat.deepseek.com/"
    _SESSION_DIR   = "deepseek_ui_session"
    _PLATFORM_NAME = "DeepSeek"

    _AUTH_URL_MARKERS      = ("login", "signin", "auth", "passport")
    _RESPONSE_FALLBACK_KEY = "send_button"
    _POST_RESPONSE_WAIT    = 5.0

    SELECTOR_CANDIDATES = _SELECTORS

    def _post_navigate(self):
        """Disable web search if it loaded in the active (selected) state."""
        try:
            toggle = self.page.locator("div.ds-toggle-button--selected[role='button']").first
            if toggle.is_visible(timeout=2_000):
                toggle.click()
                logger.info("Disabled web search toggle.")
        except Exception as e:
            logger.debug("Search toggle not found or already off: %s", e)

    def _submit_input(self):
        """Click the send button (it becomes enabled once text is typed)."""
        # Use the first resolved send_button selector that is not disabled.
        # We bypass the cache here because disabled state is dynamic.
        for candidate in self.SELECTOR_CANDIDATES["send_button"]:
            btn = self.page.locator(candidate).last
            try:
                btn.click(timeout=3_000)
                return
            except Exception:
                continue
        raise RuntimeError("Could not click DeepSeek send button — selector may need updating.")

    def wait_for_response(self):
        """Wait for DeepSeek — no stop button, so go straight to content stability."""
        try:
            # Wait for any response text to appear before we start polling.
            self.page.wait_for_selector(
                "div.ds-markdown",
                timeout=self.timeouts["response_start"],
            )
        except PWTimeoutError:
            logger.warning("No response appeared within timeout.")
            return

        # 3 s of stability (6 × 0.5 s) — slightly longer than the base default
        # because DeepSeek has no stop-button signal to give us a head start.
        self._wait_content_stable(stable_ticks=6)
        if self._POST_RESPONSE_WAIT > 0:
            time.sleep(self._POST_RESPONSE_WAIT)
        logger.info("Response received.")

    def get_active_model(self) -> str:
        _MODE_MAP = {"Instant": "DeepSeek-V3", "Thinking": "DeepSeek-R1"}
        try:
            for el in self.page.locator("div.ds-toggle-button--selected[role='button']").all():
                text = el.inner_text().strip().split("\n")[0]
                if text in _MODE_MAP:
                    return _MODE_MAP[text]
        except Exception as e:
            logger.error("Model detection failed: %s", e)
        return "Unknown"
