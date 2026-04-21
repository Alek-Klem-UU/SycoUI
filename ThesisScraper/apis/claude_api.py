from .api_base import BaseAPI


class ClaudeAPI(BaseAPI):
    _MODEL_ID      = "claude-sonnet-4-6"
    _DISPLAY_MODE  = "Sonnet 4.6"
    _PLATFORM_NAME = "Claude"

    _MAX_TOKENS = 4096

    def _make_client(self):
        # Lazy import so users running browser-only mode don't need the SDK.
        from anthropic import Anthropic, APIStatusError, APIConnectionError, RateLimitError
        self._RETRY_EXCEPTIONS = (APIStatusError, APIConnectionError, RateLimitError)
        return Anthropic(api_key=self._api_key)

    def _send(self, text: str) -> str:
        msg = self._client.messages.create(
            model=self._MODEL_ID,
            max_tokens=self._MAX_TOKENS,
            messages=[{"role": "user", "content": text}],
        )
        # content is a list of blocks; concatenate every text block so we
        # don't silently drop content if the SDK ever returns multiple.
        return "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        )
