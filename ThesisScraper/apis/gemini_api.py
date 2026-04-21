from .api_base import BaseAPI


class GeminiAPI(BaseAPI):
    _MODEL_ID      = "gemini-2.5-flash"
    _DISPLAY_MODE  = "Fast"
    _PLATFORM_NAME = "Gemini"

    def _make_client(self):
        # Lazy import so users running browser-only mode don't need the SDK.
        from google import genai
        from google.genai import errors as genai_errors
        self._RETRY_EXCEPTIONS = (genai_errors.APIError, genai_errors.ServerError)
        return genai.Client(api_key=self._api_key)

    def _send(self, text: str) -> str:
        response = self._client.models.generate_content(
            model=self._MODEL_ID,
            contents=text,
        )
        return response.text or ""
