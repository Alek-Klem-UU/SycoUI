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
        "button.__composer-pill[aria-haspopup='menu']:has-text('Instant')",
        "button.__composer-pill[aria-haspopup='menu']",
        "[data-testid='model-switcher-dropdown-button']",
        "button[data-testid*='model-switcher']",
        "button[aria-label='Model selector']",
        "button[aria-label*='Model']",
        "button[aria-haspopup='menu'][id*='model']",
        "#model-switcher",
    ],
    "model_configure": [
        "[data-testid='model-configure-modal']",
        "[role='menuitem']:has-text('Configure')",
        "[role='menuitem']:has-text('Customize')",
        "[role='menuitem']:has-text('More models')",
        "[role='option']:has-text('Configure')",
        "[role='option']:has-text('Customize')",
        "button:has-text('Configure')",
        "button:has-text('Customize')",
    ],
    "model_config_combobox": [
        "button[role='combobox'][aria-labelledby='model-selection-label']",
        "[role='dialog'] button[role='combobox']",
        "[role='dialog'] [role='combobox']",
        "button[role='combobox']:has-text('Latest')",
        "button[role='combobox']:has-text('Auto')",
        "button[role='combobox']:has-text('5.3')",
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
        "button[aria-label*='Regenerate']",
        "[data-testid='regenerate-response-button']",
    ],
}


class ChatGPTBrowser(BaseBrowser):
    _HOME_URL    = "https://chatgpt.com/"
    _LOGIN_URL   = "https://chatgpt.com/"
    _SESSION_DIR = "chatgpt_ui_session"
    _PLATFORM_NAME = "ChatGPT"
    _WINDOW_WIDTH  = 700

    _AUTH_URL_MARKERS      = ("auth.openai.com", "login")
    _RESPONSE_FALLBACK_KEY = "regenerate_button"

    SELECTOR_CANDIDATES = _SELECTORS
    TARGET_MODEL_LABEL = "GPT-5.3 Instant"
    TARGET_MODEL_MATCHES = ("GPT-5.3 Instant", "5.3 Instant", "GPT-5.3", "5.3")

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
            self._open_model_selector()

            if self._click_model_option(timeout=3_000):
                logger.info("Selected ChatGPT %s from model picker.", self.TARGET_MODEL_LABEL)
                return

            self._click_visible_candidate("model_configure", timeout=10_000)

            combobox = self._visible_candidate("model_config_combobox", timeout=15_000)
            current = self._clean_text(combobox.inner_text())
            if self._is_target_model(current):
                logger.info("ChatGPT model already configured as %s.", current)
                self._close_model_config()
                return

            self._model_select_pause()
            combobox.click()
            if not self._click_model_option(timeout=15_000):
                raise RuntimeError(
                    f"Could not find a visible {self.TARGET_MODEL_LABEL} option "
                    "in ChatGPT's model menu."
                )

            # Give the UI a moment to persist the setting before closing.
            self._model_select_pause()
            self._close_model_config()
            logger.info("Selected ChatGPT %s in model configuration.", self.TARGET_MODEL_LABEL)
        except Exception as exc:
            logger.error("Failed to select ChatGPT %s: %s", self.TARGET_MODEL_LABEL, exc)
            raise

    def _open_model_selector(self):
        """Open ChatGPT's model selector without relying on cached broad selectors."""
        selector = self._visible_candidate("model_selector", timeout=20_000)
        self._model_select_pause()
        selector.click()

    def _visible_candidate(self, key: str, timeout: int = 5_000):
        """Return the first visible locator for a selector key."""
        last_exc = None
        for candidate in self.SELECTOR_CANDIDATES.get(key, []):
            locator = self.page.locator(candidate).first
            try:
                locator.wait_for(state="visible", timeout=timeout)
                logger.debug("Visible selector resolved for '%s': %s", key, candidate)
                return locator
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(
            f"No visible ChatGPT selector for '{key}'. "
            f"Tried: {self.SELECTOR_CANDIDATES.get(key, [])}."
        ) from last_exc

    def _click_visible_candidate(self, key: str, timeout: int = 5_000):
        locator = self._visible_candidate(key, timeout=timeout)
        self._model_select_pause()
        locator.click()
        return locator

    def _click_model_option(self, timeout: int = 5_000) -> bool:
        """Click the best visible target-model option in the open picker/listbox."""
        deadline = time.monotonic() + (timeout / 1000)
        option_selector = "[role='option'], [role='menuitem'], [cmdk-item], button"
        for text in self.TARGET_MODEL_MATCHES:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                return False
            option = self.page.locator(option_selector).filter(has_text=text).first
            try:
                option.wait_for(state="visible", timeout=min(300, remaining_ms))
                time.sleep(random.uniform(0.05, 0.15))
                option.click()
                return True
            except Exception:
                continue
        return False

    @classmethod
    def _is_target_model(cls, text: str) -> bool:
        return any(match in text for match in cls.TARGET_MODEL_MATCHES)

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _model_select_pause():
        """Small jitter between model-picker interactions."""
        time.sleep(random.uniform(0.25, 0.75))

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
