"""Anthropic (Claude) assembly provider."""

from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel

from .base import AssemblyProvider, ProviderError

T = TypeVar("T", bound=BaseModel)

_MAX_TOKENS = 16000


class ClaudeAssembly(AssemblyProvider):
    """Structured + text generation via the Anthropic Messages API."""

    def __init__(self, model: str, api_key: str | None):
        super().__init__(model, api_key)
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise ProviderError(
                "The Anthropic SDK is required for --llm claude. "
                "Install with: pip install 'slide-gen[claude]'"
            ) from exc
        if not api_key:
            raise ProviderError(
                "No Anthropic API key. Set ANTHROPIC_API_KEY or pass --anthropic-api-key."
            )
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate_structured(self, system: str, user: str, schema: Type[T]) -> T:
        message = self._client.messages.parse(
            model=self.model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if message.parsed_output is None:
            raise ProviderError("Claude returned no parseable structured output.")
        return message.parsed_output

    def generate_text(self, system: str, user: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in message.content if b.type == "text").strip()
