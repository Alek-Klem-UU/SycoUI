from .api_base import BaseAPI


class DeepSeekAPI(BaseAPI):
    _MODEL_ID      = "deepseek-v4-flash"
    _DISPLAY_MODE  = "DeepSeek-V4"
    _PLATFORM_NAME = "DeepSeek"

    _BASE_URL   = "https://api.deepseek.com"
    _MAX_TOKENS = 4096

    def _make_client(self):
        # Lazy import so users running browser-only mode don't need the SDK.
        # DeepSeek exposes an OpenAI-compatible API, so we reuse the openai SDK.
        from openai import OpenAI, APIStatusError, APIConnectionError, RateLimitError
        self._RETRY_EXCEPTIONS = (APIStatusError, APIConnectionError, RateLimitError)
        return OpenAI(api_key=self._api_key, base_url=self._BASE_URL)

    def _send(self, text: str) -> str:
        kwargs = {}
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature

        response = self._client.chat.completions.create(
            model=self._MODEL_ID,
            max_tokens=self._MAX_TOKENS,
            messages=[{"role": "user", "content": text}],
            extra_body={
               "thinking": {"type": "disabled"}
            },
            **kwargs,
        )
        return response.choices[0].message.content or ""
