"""OpenAI (GPT) assembly provider — the default."""

from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel

from .base import AssemblyProvider, ProviderError

T = TypeVar("T", bound=BaseModel)


class OpenAIAssembly(AssemblyProvider):
    """Structured + text generation via the OpenAI Responses API."""

    def __init__(self, model: str, api_key: str | None):
        super().__init__(model, api_key)
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - import guard
            raise ProviderError(
                "The OpenAI SDK is required for --llm gpt. Install with: pip install 'slide-gen[gpt]'"
            ) from exc
        if not api_key:
            raise ProviderError("No OpenAI API key. Set OPENAI_API_KEY or pass --openai-api-key.")
        self._client = OpenAI(api_key=api_key)

    def generate_structured(self, system: str, user: str, schema: Type[T]) -> T:
        response = self._client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=schema,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ProviderError("OpenAI returned no parseable structured output.")
        return parsed

    def generate_text(self, system: str, user: str) -> str:
        response = self._client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.output_text or "").strip()
