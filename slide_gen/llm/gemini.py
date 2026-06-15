"""Google (Gemini) assembly provider."""

from __future__ import annotations

import json
from typing import Type, TypeVar

from pydantic import BaseModel

from .base import AssemblyProvider, ProviderError

T = TypeVar("T", bound=BaseModel)


class GeminiAssembly(AssemblyProvider):
    """Structured + text generation via the google-genai SDK."""

    def __init__(self, model: str, api_key: str | None):
        super().__init__(model, api_key)
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - import guard
            raise ProviderError(
                "The google-genai SDK is required for --llm gemini. "
                "Install with: pip install 'slide-gen[gemini]'"
            ) from exc
        if not api_key:
            raise ProviderError(
                "No Gemini API key. Set GEMINI_API_KEY/GOOGLE_API_KEY or pass --gemini-api-key."
            )
        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def generate_structured(self, system: str, user: str, schema: Type[T]) -> T:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        # SDK populates `.parsed` with the pydantic instance when given a schema;
        # fall back to parsing the JSON text if not.
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        if response.text:
            return schema.model_validate(json.loads(response.text))
        raise ProviderError("Gemini returned no parseable structured output.")

    def generate_text(self, system: str, user: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return (response.text or "").strip()
