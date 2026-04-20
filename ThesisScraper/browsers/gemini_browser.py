import logging
from .browser_base import BaseBrowser

logger = logging.getLogger(__name__)


_SELECTORS = {
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
    "message_body": [
        ".message-content, .markdown, response-body",
        "[data-test-id='response-body']",
    ],
}


class GeminiBrowser(BaseBrowser):
    _HOME_URL    = "https://gemini.google.com/app"
    _LOGIN_URL   = "https://gemini.google.com/app"
    _SESSION_DIR = "gemini_ui_session"
    _PLATFORM_NAME = "Gemini"

    _AUTH_URL_MARKERS      = ("signin", "accounts.google")
    _RESPONSE_FALLBACK_KEY = "mic_button"

    SELECTOR_CANDIDATES = _SELECTORS

    def get_active_model(self) -> str:
        try:
            for pill in self.page.locator(self._selector("model_pill")).all():
                if pill.is_visible():
                    raw = pill.inner_text().split("\n")[0]
                    return raw.replace("keyboard_arrow_down", "").strip()
        except Exception as e:
            logger.error("Model detection failed: %s", e)
        return "Unknown"
