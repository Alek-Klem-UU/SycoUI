from .api_base import BaseAPI


class ChatGPTAPI(BaseAPI):
    _MODEL_ID      = "gpt-5.3-chat-latest"
    _DISPLAY_MODE  = "ChatGPT"
    _PLATFORM_NAME = "ChatGPT"

    def _make_client(self):
        # Lazy import so users running browser-only mode don't need the SDK.
        from openai import OpenAI, APIStatusError, APIConnectionError, RateLimitError
        self._RETRY_EXCEPTIONS = (APIStatusError, APIConnectionError, RateLimitError)
        return OpenAI(api_key=self._api_key)

    def _send(self, text: str) -> str:
        kwargs = {}
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature

        completion = self._client.chat.completions.create(
            model=self._MODEL_ID,
            messages=[{"role": "user", "content": text}],
            **kwargs,
        )
        return completion.choices[0].message.content or ""
