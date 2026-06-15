"""Provider-agnostic image generation interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ImageProviderError(Exception):
    """Raised for image-provider/SDK/configuration problems."""


class ImageProvider(ABC):
    """An image model that turns a text prompt into PNG bytes."""

    def __init__(self, model: str, api_key: str | None):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    def generate(self, prompt: str, size: str) -> bytes:
        """Return PNG image bytes for ``prompt`` at ``size`` (e.g. '1024x1024')."""


_REGISTRY: dict[str, str] = {
    "gpt": "slide_gen.images.openai_image:OpenAIImage",
    "gemini": "slide_gen.images.gemini_image:GeminiImage",
}


def get_image_provider(name: str, model: str, api_key: str | None) -> ImageProvider:
    import importlib

    if name not in _REGISTRY:
        raise ImageProviderError(
            f"Unknown image provider '{name}'. Choose one of: {', '.join(_REGISTRY)}."
        )
    module_path, class_name = _REGISTRY[name].split(":")
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(model=model, api_key=api_key)
