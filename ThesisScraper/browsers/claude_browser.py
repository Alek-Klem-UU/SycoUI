import logging
from .browser_base import BaseBrowser

logger = logging.getLogger(__name__)


_SELECTORS = {
    "chat_input": [
        "div.ProseMirror[contenteditable='true']",
        "div[contenteditable='true']",
        "[data-testid='chat-input']",
    ],
    "send_button": [
        "button[aria-label='Send Message']",
        "button[type='button'][aria-label*='Send']",
        "button[data-testid='send-button']",
    ],
    "stop_button": [
        "button[aria-label='Stop Response']",
        "button[aria-label*='Stop']",
        "button[data-testid='stop-button']",
    ],
    "response_complete_signal": [
        # The Copy button only appears after a response finishes — most
        # reliable completion signal for claude.ai.
        "button[aria-label='Copy response']",
        "button[aria-label*='Copy']",
        "button[data-testid='copy-response-button']",
    ],
    "model_pill": [
        "button[data-testid='model-selector-dropdown']",
        "button[aria-haspopup='listbox']",
        "[data-testid='model-selector']",
    ],
    "user_query": [
        "div[data-testid='user-message']",
        ".font-user-message",
        "[class*='HumanMessage']",
    ],
    "response_node": [
        "div.standard-markdown",
        "[class*='standard-markdown']",
        "div[data-testid='assistant-message']",
        ".font-claude-message",
        "[class*='AssistantMessage']",
    ],
    "message_body": [
        ".font-claude-response-body",
        "div.standard-markdown",
        "div[data-testid='assistant-message'] .prose, "
        "div[data-testid='assistant-message'] [class*='prose'], "
        ".font-claude-message .prose",
        "div[data-testid='assistant-message']",
    ],
}


class ClaudeBrowser(BaseBrowser):
    _HOME_URL    = "https://claude.ai/new"
    _LOGIN_URL   = "https://claude.ai/login"
    _SESSION_DIR = "claude_ui_session"
    _PLATFORM_NAME = "Claude"

    _AUTH_URL_MARKERS      = ("login", "auth", "signin", "accounts.google")
    _RESPONSE_FALLBACK_KEY = "response_complete_signal"

    SELECTOR_CANDIDATES = _SELECTORS

    def _submit_input(self):
        """Claude uses a dedicated send button instead of Enter."""
        self.page.locator(self._selector("send_button")).click()

    def get_active_model(self) -> str:
        try:
            for pill in self.page.locator(self._selector("model_pill")).all():
                if pill.is_visible():
                    return pill.inner_text().strip().replace("\n", "")
        except Exception as e:
            logger.error("Model detection failed: %s", e)
        return "Unknown"
