import logging
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
        "button[aria-haspopup='menu'][id*='model']",
        "#model-switcher",
        "button.text-token-text-primary span",
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

    def get_active_model(self) -> str:
        try:
            locator = self.page.locator(self._selector("model_selector")).first
            if locator.is_visible():
                raw = locator.inner_text().strip()
                return raw.split("\n")[0].strip()
        except Exception as e:
            logger.error("Model detection failed: %s", e)
        return "Unknown"
