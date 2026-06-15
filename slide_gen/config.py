"""Central configuration: default models, env-var names, and resolved settings.

Default model IDs change over time. They are plain constants here and every one
is overridable from the CLI (``--llm-model`` / ``--image-model``), so adapting to
a new model release is a one-line edit or a single flag.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --- Assembly (text) LLM defaults -------------------------------------------------
DEFAULT_LLM_PROVIDER = "gpt"  # gpt | claude | gemini

DEFAULT_LLM_MODELS = {
    "gpt": "gpt-5.5",
    "claude": "claude-opus-4-8",
    "gemini": "gemini-3-pro",
}

# --- Image generation defaults ----------------------------------------------------
DEFAULT_IMAGE_PROVIDER = "gpt"  # gpt | gemini

DEFAULT_IMAGE_MODELS = {
    "gpt": "gpt-image-2",
    "gemini": "gemini-3-pro-image",
}

# --- API-key environment variables (per provider company) -------------------------
# Providers are grouped by the company whose key they use.
ENV_KEYS = {
    "gpt": ["OPENAI_API_KEY"],
    "claude": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
}

DEFAULT_MAX_REPAIR_ATTEMPTS = 2
DEFAULT_IMAGE_SIZE = "1024x1024"
DEFAULT_IMAGE_WORKERS = 3  # keep image bursts under typical per-minute limits


def resolve_api_key(provider: str, override: Optional[str]) -> Optional[str]:
    """Return an explicit override, else the first matching env var, else None."""
    if override:
        return override
    for env_name in ENV_KEYS.get(provider, []):
        value = os.environ.get(env_name)
        if value:
            return value
    return None


@dataclass
class Settings:
    """Fully resolved run configuration passed through the pipeline."""

    inputs: list[Path]
    output: Path

    # Assembly LLM
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: Optional[str] = None  # None -> DEFAULT_LLM_MODELS[provider]
    llm_api_key: Optional[str] = None

    # Image generation
    images: bool = False
    image_provider: str = DEFAULT_IMAGE_PROVIDER
    image_model: Optional[str] = None  # None -> DEFAULT_IMAGE_MODELS[provider]
    image_api_key: Optional[str] = None
    image_size: str = DEFAULT_IMAGE_SIZE

    # Content steering
    max_slides: Optional[int] = None
    audience: Optional[str] = None
    tone: Optional[str] = None
    instructions: Optional[str] = None
    theme_hint: Optional[str] = None

    # Build options
    work_dir: Optional[Path] = None
    keep_tex: bool = False
    resume: bool = False
    max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS
    verbose: bool = False

    def resolved_llm_model(self) -> str:
        return self.llm_model or DEFAULT_LLM_MODELS[self.llm_provider]

    def resolved_image_model(self) -> str:
        return self.image_model or DEFAULT_IMAGE_MODELS[self.image_provider]
