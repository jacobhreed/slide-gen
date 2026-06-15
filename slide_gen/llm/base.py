"""Provider-agnostic interface for structured + freeform text generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderError(Exception):
    """Raised for provider/SDK/configuration problems."""


class AssemblyProvider(ABC):
    """A text LLM that can return validated structured output and freeform text."""

    def __init__(self, model: str, api_key: str | None):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    def generate_structured(self, system: str, user: str, schema: Type[T]) -> T:
        """Return an instance of ``schema`` populated by the model."""

    @abstractmethod
    def generate_text(self, system: str, user: str) -> str:
        """Return freeform text (used by the LaTeX repair loop)."""


# Registry: provider key -> "module:ClassName". Lazy-imported so installing one
# provider SDK doesn't require the others. Adding a provider is a one-line change.
_REGISTRY: dict[str, str] = {
    "gpt": "slide_gen.llm.openai_provider:OpenAIAssembly",
    "claude": "slide_gen.llm.claude:ClaudeAssembly",
    "gemini": "slide_gen.llm.gemini:GeminiAssembly",
}


def get_assembly_provider(name: str, model: str, api_key: str | None) -> AssemblyProvider:
    import importlib

    if name not in _REGISTRY:
        raise ProviderError(
            f"Unknown LLM provider '{name}'. Choose one of: {', '.join(_REGISTRY)}."
        )
    module_path, class_name = _REGISTRY[name].split(":")
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(model=model, api_key=api_key)
