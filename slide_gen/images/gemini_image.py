"""Gemini image provider (gemini-3-pro-image by default)."""

from __future__ import annotations

from .base import ImageProvider, ImageProviderError


class GeminiImage(ImageProvider):
    def __init__(self, model: str, api_key: str | None):
        super().__init__(model, api_key)
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImageProviderError(
                "The google-genai SDK is required for --image-provider gemini. "
                "Install with: pip install 'slide-gen[gemini]'"
            ) from exc
        if not api_key:
            raise ImageProviderError(
                "No Gemini API key. Set GEMINI_API_KEY/GOOGLE_API_KEY or pass --gemini-api-key."
            )
        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, size: str) -> bytes:
        # Gemini image models infer aspect from the prompt; `size` is advisory.
        response = self._client.models.generate_content(
            model=self.model,
            contents=f"{prompt}\n\n(Target a {size} px square composition.)",
        )
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    return inline.data
        raise ImageProviderError("Gemini image response contained no image data.")
