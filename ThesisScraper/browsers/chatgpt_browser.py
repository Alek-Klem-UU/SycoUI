import logging
import random
import time

from patchright.sync_api import TimeoutError as PWTimeoutError

from .browser_base import BaseBrowser

logger = logging.getLogger(__name__)


_SELECTORS = {
    "chat_input": [
        "#prompt-textarea",
        "div[id='prompt-textarea']",
        "textarea[placeholder*='Message']",
        "div[contenteditable='true'][data-id='root']",
        "div[contenteditable='true']",
    ],
    "send_button": [
        "[data-testid='send-button']",
        "button[aria-label='Send message']",
        "button[aria-label*='Send']",
        "button[data-testid='fruitjuice-send-button']",
    ],
    "stop_button": [
        "button[aria-label='Stop streaming']",
        "button[aria-label*='Stop']",
        "[data-testid='stop-button']",
    ],
    "model_selector": [
        "[data-testid='model-switcher-dropdown-button']",
        "button[aria-label='Model selector']",
        "button[aria-haspopup='menu'][id*='model']",
        "#model-switcher",
        "button.text-token-text-primary span",
    ],
    "model_configure": [
        "[data-testid='model-configure-modal']",
        "[role='menuitem']:has-text('Configure')",
    ],
    "model_config_combobox": [
        "button[role='combobox'][aria-labelledby='model-selection-label']",
        "button[role='combobox']:has-text('Latest')",
        "button[role='combobox']:has-text('5.5')",
    ],
    "model_config_dialog": [
        "[role='dialog']",
    ],
    "response_node": [
        "[data-message-author-role='assistant']",
        "[data-testid*='conversation-turn'] [data-message-author-role='assistant']",
        ".agent-turn",
    ],
    "user_query": [
        "[data-message-author-role='user']",
        "[data-testid*='conversation-turn'] [data-message-author-role='user']",
    ],
    "message_body": [
        ".markdown.prose",
        "[data-message-author-role='assistant'] .markdown",
        ".text-message",
        "[data-testid='message-content']",
    ],
    "regenerate_button": [
        "button[aria-label='Regenerate']",
        "[data-testid='regenerate-response-button']",
    ],
}


class ChatGPTBrowser(BaseBrowser):
    _HOME_URL    = "https://chatgpt.com/"
    _LOGIN_URL   = "https://chatgpt.com/"
    _SESSION_DIR = "chatgpt_ui_session"
    _PLATFORM_NAME = "ChatGPT"
    _WINDOW_WIDTH  = 400

    _AUTH_URL_MARKERS      = ("auth.openai.com", "login")
    _RESPONSE_FALLBACK_KEY = "regenerate_button"

    SELECTOR_CANDIDATES = _SELECTORS

    DEFAULT_TIMEOUTS = {
        **BaseBrowser.DEFAULT_TIMEOUTS,
        "response_start": 8_000,
    }

    def _post_navigate(self):
        """Force ChatGPT browser runs onto GPT-5.3 Instant before prompting."""
        self.select_gpt53_instant()

    def select_gpt53_instant(self):
        """Open ChatGPT's model configuration UI and select GPT-5.3 Instant."""
        try:
            selector = self.page.locator(self._selector("model_selector")).first
            selector.wait_for(state="visible", timeout=20_000)
            self._model_select_pause()
            selector.click()

            configure = self.page.locator(self._selector("model_configure")).first
            configure.wait_for(state="visible", timeout=10_000)
            self._model_select_pause()
            configure.click()

            combobox = self.page.locator(self._selector("model_config_combobox")).first
            combobox.wait_for(state="visible", timeout=15_000)

            current = combobox.inner_text().strip()
            if "5.3" in current:
                logger.info("ChatGPT model already configured as %s.", current)
                self._close_model_config()
                return

            self._model_select_pause()
            combobox.click()
            option = self.page.locator("[role='option']").filter(has_text="5.3").first
            option.wait_for(state="visible", timeout=15_000)
            self._model_select_pause()
            option.click()

            # Give the UI a moment to persist the setting before closing.
            self._model_select_pause()
            self._close_model_config()
            logger.info("Selected ChatGPT GPT-5.3 Instant in model configuration.")
        except Exception as exc:
            logger.error("Failed to select ChatGPT GPT-5.3 Instant: %s", exc)
            raise

    @staticmethod
    def _model_select_pause():
        """Small jitter between model-picker interactions."""
        time.sleep(random.uniform(1.0, 3.0))

    def _close_model_config(self):
        """Close the ChatGPT model configuration dialog if it is open."""
        try:
            close_button = self.page.locator(
                "[role='dialog'] button[aria-label='Close'], "
                "[role='dialog'] button:has-text('Done')"
            ).first
            if close_button.is_visible():
                close_button.click()
                return
        except Exception:
            pass

        # Radix menus/dialogs consistently close on Escape; use it as fallback.
        self.page.keyboard.press("Escape")
        self.page.keyboard.press("Escape")
        try:
            self.page.locator("[role='dialog']").first.wait_for(
                state="hidden", timeout=3_000
            )
        except PWTimeoutError:
            logger.debug("Model configuration dialog did not report hidden after Escape.")
        except Exception:
            # If the dialog is already detached, the close succeeded.
            pass

    def get_active_model(self) -> str:
        try:
            locator = self.page.locator(self._selector("model_selector")).first
            if locator.is_visible():
                raw = locator.inner_text().strip()
                return raw.split("\n")[0].strip()
        except Exception as e:
            logger.error("Model detection failed: %s", e)
        return "Unknown"
