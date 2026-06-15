"""Command-line interface for slide-gen."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from .config import (
    DEFAULT_IMAGE_PROVIDER,
    DEFAULT_LLM_PROVIDER,
    Settings,
)
from .pipeline import PipelineError, generate_deck


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), default=Path("deck.pdf"),
              show_default=True, help="Output PDF path.")
# Assembly LLM
@click.option("--llm", "llm_provider", type=click.Choice(["gpt", "claude", "gemini"]),
              default=DEFAULT_LLM_PROVIDER, show_default=True, help="Assembly LLM provider.")
@click.option("--llm-model", default=None, help="Override the specific assembly model name.")
# Images
@click.option("--images/--no-images", default=False, show_default=True,
              help="Generate and embed AI graphics.")
@click.option("--image-provider", type=click.Choice(["gpt", "gemini"]),
              default=DEFAULT_IMAGE_PROVIDER, show_default=True, help="Image-generation provider.")
@click.option("--image-model", default=None, help="Override the specific image model name.")
@click.option("--image-size", default=None, help="Image size, e.g. 1024x1024.")
# Content steering
@click.option("--max-slides", type=int, default=None, help="Approximate upper bound on slide count.")
@click.option("--audience", default=None, help="Target audience.")
@click.option("--tone", default=None, help="Desired tone (e.g. 'formal', 'energetic').")
@click.option("--instructions", default=None, help="Freeform extra instructions.")
@click.option("--theme-hint", default=None, help="Optional design steer for the LLM-chosen theme.")
# API keys
@click.option("--openai-api-key", default=None, help="OpenAI key (else $OPENAI_API_KEY).")
@click.option("--anthropic-api-key", default=None, help="Anthropic key (else $ANTHROPIC_API_KEY).")
@click.option("--gemini-api-key", default=None, help="Gemini key (else $GEMINI_API_KEY/$GOOGLE_API_KEY).")
# Build options
@click.option("--work-dir", type=click.Path(path_type=Path), default=None,
              help="Directory for intermediate files (default: temp dir).")
@click.option("--keep-tex", is_flag=True, default=False, help="Keep the generated .tex next to the PDF.")
@click.option("--resume", is_flag=True, default=False,
              help="Reuse cached plan/content/images from a prior run and finish what's left.")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose progress output.")
def main(
    inputs: tuple[Path, ...],
    output: Path,
    llm_provider: str,
    llm_model: Optional[str],
    images: bool,
    image_provider: str,
    image_model: Optional[str],
    image_size: Optional[str],
    max_slides: Optional[int],
    audience: Optional[str],
    tone: Optional[str],
    instructions: Optional[str],
    theme_hint: Optional[str],
    openai_api_key: Optional[str],
    anthropic_api_key: Optional[str],
    gemini_api_key: Optional[str],
    work_dir: Optional[Path],
    keep_tex: bool,
    resume: bool,
    verbose: bool,
) -> None:
    """Generate a production-ready slide deck (PDF) from INPUTS (files or folders)."""
    from rich.console import Console
    from rich.markup import escape

    console = Console(stderr=True)

    # Map per-company keys to the chosen providers.
    llm_key = {"gpt": openai_api_key, "claude": anthropic_api_key, "gemini": gemini_api_key}[llm_provider]
    image_key = {"gpt": openai_api_key, "gemini": gemini_api_key}[image_provider]

    settings = Settings(
        inputs=list(inputs),
        output=output,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_key,
        images=images,
        image_provider=image_provider,
        image_model=image_model,
        image_api_key=image_key,
        max_slides=max_slides,
        audience=audience,
        tone=tone,
        instructions=instructions,
        theme_hint=theme_hint,
        work_dir=work_dir,
        keep_tex=keep_tex,
        resume=resume,
        verbose=verbose,
    )
    if image_size:
        settings.image_size = image_size

    def log(message: str) -> None:
        console.print(message, markup=False)

    try:
        with console.status("[bold]Generating deck...", spinner="dots"):
            result = generate_deck(settings, log=log if verbose else None)
        console.print(f"[green]✓[/green] Wrote [bold]{escape(str(result))}[/bold]")
    except PipelineError as exc:
        console.print("[red]Error:[/red]", escape(str(exc)))
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the user
        console.print("[red]Error:[/red]", escape(str(exc)))
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
