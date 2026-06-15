"""OpenAI image provider (gpt-image-2 by default)."""

from __future__ import annotations

import base64
import re
import time

from .base import ImageProvider, ImageProviderError

# Rate limits are transient: wait them out rather than skipping the image. With a
# per-minute cap the window always resets, so a generous retry budget effectively
# means "keep waiting until the limit clears."
_MAX_RATE_LIMIT_RETRIES = 30
_DEFAULT_BACKOFF_SECONDS = 15.0
_MAX_BACKOFF_SECONDS = 60.0


def _retry_after_seconds(message: str) -> float:
    """Parse 'try again in 12s' / 'in 1.5s' from a rate-limit message."""
    match = re.search(r"try again in\s+([0-9.]+)\s*s", message, re.IGNORECASE)
    if match:
        try:
            return min(float(match.group(1)) + 1.0, _MAX_BACKOFF_SECONDS)  # safety margin
        except ValueError:
            pass
    return _DEFAULT_BACKOFF_SECONDS


class OpenAIImage(ImageProvider):
    def __init__(self, model: str, api_key: str | None):
        super().__init__(model, api_key)
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImageProviderError(
                "The OpenAI SDK is required for --image-provider gpt. "
                "Install with: pip install 'slide-gen[gpt]'"
            ) from exc
        if not api_key:
            raise ImageProviderError(
                "No OpenAI API key. Set OPENAI_API_KEY or pass --openai-api-key."
            )
        self._client = OpenAI(api_key=api_key)

    def generate(self, prompt: str, size: str) -> bytes:
        try:
            from openai import RateLimitError
        except ImportError:  # pragma: no cover - openai is guaranteed present here
            RateLimitError = ()  # type: ignore[assignment]

        last_exc: Exception | None = None
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            try:
                result = self._client.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size=size,
                )
                break
            except RateLimitError as exc:  # transient: wait and retry
                last_exc = exc
                if attempt == _MAX_RATE_LIMIT_RETRIES:
                    raise
                time.sleep(_retry_after_seconds(str(exc)))
        else:  # pragma: no cover - loop always breaks or raises
            raise ImageProviderError(str(last_exc))

        data = result.data[0]
        if getattr(data, "b64_json", None):
            return base64.b64decode(data.b64_json)
        # Some models return a URL instead of inline base64.
        url = getattr(data, "url", None)
        if url:
            import urllib.request

            with urllib.request.urlopen(url) as resp:  # noqa: S310 - trusted OpenAI URL
                return resp.read()
        raise ImageProviderError("OpenAI image response contained no image data.")
