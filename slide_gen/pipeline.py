"""End-to-end orchestration: ingest -> plan -> write -> images -> render -> compile.

Supports ``--resume``: plan, deck content, and generated images are cached on disk
so an interrupted run (e.g. an image rate-limit or a Ctrl-C during repair) can be
restarted and only the missing work is redone.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from . import prompts
from .config import DEFAULT_IMAGE_WORKERS, Settings, resolve_api_key
from .images import get_image_provider
from .ingest import build_corpus
from .llm import AssemblyProvider, get_assembly_provider
from .models import DeckPlan, DeckSpec, Slide
from .render import compile_pdf, render_latex

Logger = Callable[[str], None]
M = TypeVar("M", bound=BaseModel)


class PipelineError(Exception):
    """Raised when the deck cannot be produced."""


def _noop(_: str) -> None:
    pass


def _strip_code_fence(text: str) -> str:
    """Remove a leading/trailing markdown code fence if the model added one."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip() + "\n"


def _resolve_work_dir(settings: Settings) -> tuple[Path, bool]:
    """Return (work_dir, is_temp). Persistent when --work-dir or --resume is set."""
    if settings.work_dir is not None:
        return Path(settings.work_dir), False
    if settings.resume:
        # Stable, output-derived location so a rerun finds prior artifacts.
        return settings.output.parent / f".slide-gen-{settings.output.stem}", False
    return Path(tempfile.mkdtemp(prefix="slide-gen-")), True


def _cached_stage(
    provider: AssemblyProvider,
    system: str,
    user: str,
    schema: Type[M],
    cache_path: Path,
    resume: bool,
    log: Logger,
    label: str,
) -> M:
    """Run a structured LLM stage, reusing a cached JSON result when resuming.

    A cache file that doesn't match the current schema (e.g. produced by an older
    version) is ignored and regenerated rather than crashing the run.
    """
    if resume and cache_path.exists():
        try:
            result = schema.model_validate_json(cache_path.read_text(encoding="utf-8"))
            log(f"  Resuming: loaded cached {label} from {cache_path.name}")
            return result
        except ValidationError:
            log(f"  Cached {label} is incompatible with the current version; regenerating.")
    result = provider.generate_structured(system, user, schema)
    cache_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def _image_filename(idx: int, prompt: str) -> str:
    digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:8]
    return f"slide_{idx + 1:02d}_{digest}.png"


def _hex(value: str) -> str:
    v = (value or "").strip()
    return v if v.startswith("#") else f"#{v}" if v else ""


def _fmt_num(value: float) -> str:
    return str(int(value)) if value == int(value) else repr(value)


def _slide_facts(slide: Slide) -> list[str]:
    """Collect the concrete facts a generated image should depict accurately."""
    facts: list[str] = list(slide.visual.image_facts)
    facts += [f"{_fmt_num(d.value)} ({d.label})" for d in slide.visual.chart_data]
    facts += [f"{t.date}: {t.label}" for t in slide.visual.timeline]
    facts += [f"{m.value} {m.label}" for m in slide.visual.metrics]
    facts += [b for b in slide.bullets if b.strip()]
    # De-duplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for f in facts:
        f = f.strip()
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _build_image_prompt(deck: DeckSpec, slide: Slide) -> str:
    """Assemble a rich, data-driven, branded prompt from the writer's direction,
    the slide's real facts, the deck palette, and smart anti-competitor guardrails."""
    style = deck.style
    parts: list[str] = [slide.visual.image_prompt.strip()]

    facts = _slide_facts(slide)
    if facts:
        parts.append(
            "Depict this information accurately, with clean correctly-spelled labels and "
            "exact numbers: " + "; ".join(facts) + "."
        )

    brand = (deck.brand_name or "").strip()
    if brand:
        parts.append(
            f"This graphic is for {brand}. Where the visual is branded, label it clearly "
            f"and correctly as \"{brand}\"."
        )

    motif = (style.visual_motif or "").strip()
    palette = ", ".join(
        c for c in (
            _hex(style.primary_color), _hex(style.secondary_color),
            _hex(style.accent_color), _hex(style.background_color),
        ) if c
    )
    style_bits = []
    if motif:
        style_bits.append(motif)
    if palette:
        style_bits.append(f"use this exact color palette: {palette}")
    style_bits.append("modern, clean, professional, generous whitespace, high contrast, no clutter")
    parts.append("Style: " + "; ".join(style_bits) + ".")

    # Smart guardrail: allow this brand + accurate text; forbid OTHER brands and
    # competitor-associated real places that derail the model.
    guard = (
        "Do not include any other real company, bank, brand, logo, or trademark, and do "
        "not depict real city skylines, landmarks, maps, or identifiable real people. "
    )
    if brand:
        guard += f"The only brand shown may be {brand}. "
    guard += "All text must be legible and spelled correctly."
    parts.append(guard)

    return " ".join(p for p in parts if p)


def _generate_images(
    deck: DeckSpec, settings: Settings, image_dir: Path, log: Logger
) -> dict[int, Path]:
    """Generate images for slides that requested one. Failures are skipped;
    already-present files (from a prior run) are reused."""
    targets = [
        (idx, _build_image_prompt(deck, slide))
        for idx, slide in enumerate(deck.slides)
        if slide.visual.kind == "image" and slide.visual.image_prompt.strip()
    ]
    if not targets:
        return {}

    image_dir.mkdir(parents=True, exist_ok=True)
    results: dict[int, Path] = {}
    pending: list[tuple[int, str, Path]] = []
    for idx, prompt in targets:
        out = image_dir / _image_filename(idx, prompt)
        if out.exists() and out.stat().st_size > 0:
            results[idx] = out  # reuse from a previous run
        else:
            pending.append((idx, prompt, out))

    if results:
        log(f"  Reusing {len(results)} cached image(s).")
    if not pending:
        return results

    api_key = resolve_api_key(settings.image_provider, settings.image_api_key)
    provider = get_image_provider(
        settings.image_provider, settings.resolved_image_model(), api_key
    )

    def _one(idx: int, prompt: str, out: Path) -> tuple[int, Optional[Path]]:
        try:
            data = provider.generate(prompt, settings.image_size)
        except Exception as exc:  # noqa: BLE001 - one bad image must not kill the deck
            log(f"  [warn] image for slide {idx + 1} failed: {exc}")
            return idx, None
        out.write_bytes(data)
        return idx, out

    log(f"Generating {len(pending)} image(s) with {settings.image_provider}"
        f" ({settings.resolved_image_model()})...")
    with ThreadPoolExecutor(max_workers=DEFAULT_IMAGE_WORKERS) as pool:
        futures = [pool.submit(_one, idx, prompt, out) for idx, prompt, out in pending]
        for future in as_completed(futures):
            idx, path = future.result()
            if path is not None:
                results[idx] = path
    succeeded = len(results)
    total = len(targets)
    log(f"  {succeeded}/{total} image(s) available"
        + ("" if succeeded == total else " (rerun with --resume to retry the rest)."))
    return results


def _log_error_tail(log: Logger, error_log: str, lines: int = 14) -> None:
    log("  --- LaTeX error (tail) ---")
    for line in error_log.splitlines()[-lines:]:
        log("  " + line)
    log("  --------------------------")


def generate_deck(settings: Settings, log: Optional[Logger] = None) -> Path:
    """Run the full pipeline and return the path to the finished PDF."""
    log = log or _noop

    # 1. Ingest
    log("Reading source material...")
    corpus = build_corpus(settings.inputs)

    # 2. Assembly provider
    api_key = resolve_api_key(settings.llm_provider, settings.llm_api_key)
    provider = get_assembly_provider(
        settings.llm_provider, settings.resolved_llm_model(), api_key
    )

    work_dir, is_temp = _resolve_work_dir(settings)
    work_dir.mkdir(parents=True, exist_ok=True)
    completed = False

    try:
        # 3. Plan (structure + style) — cached for resume
        log(f"Planning deck with {settings.llm_provider} ({settings.resolved_llm_model()})...")
        plan: DeckPlan = _cached_stage(
            provider, prompts.PLANNER_SYSTEM, prompts.planner_user(corpus, settings),
            DeckPlan, work_dir / "plan.json", settings.resume, log, "plan",
        )
        log(f"  Planned {len(plan.slides)} slide(s): \"{plan.title}\"")

        # 4. Write full content — cached for resume
        log("Writing slide content...")
        deck: DeckSpec = _cached_stage(
            provider, prompts.WRITER_SYSTEM,
            prompts.writer_user(corpus, plan.model_dump_json(indent=2), settings),
            DeckSpec, work_dir / "deck.json", settings.resume, log, "deck",
        )
        # Guarantee design + title consistency with the approved plan.
        deck.style = plan.style
        if not deck.title:
            deck.title = plan.title
        if not deck.subtitle:
            deck.subtitle = plan.subtitle
        if not deck.brand_name:
            deck.brand_name = plan.brand_name
        log(f"  Wrote {len(deck.slides)} slide(s).")

        # 5. Images (optional, cached/reused on disk)
        images: dict[int, Path] = {}
        if settings.images:
            images = _generate_images(deck, settings, work_dir / "images", log)

        # 6. Render LaTeX
        log("Rendering LaTeX...")
        tex_source = render_latex(deck, images)
        tex_path = work_dir / "deck.tex"
        tex_path.write_text(tex_source, encoding="utf-8")

        # 7. Compile, with an LLM repair loop on *source* errors only
        log("Compiling PDF...")
        result = compile_pdf(tex_path, work_dir)
        if not result.success and result.engine_error:
            # The LaTeX engine itself could not run — repairing the source won't
            # help, so fail fast with an actionable message.
            raise PipelineError(
                "The LaTeX engine could not run (this is a toolchain problem, not "
                "a content problem). On MiKTeX, 'latexmk' needs Perl; 'pdflatex' "
                "should work on its own — ensure it is installed and on your PATH. "
                f"Source kept at: {tex_path}\nEngine output (tail):\n{result.log}"
            )
        attempt = 0
        while not result.success and attempt < settings.max_repair_attempts:
            attempt += 1
            _log_error_tail(log, result.log)
            log(f"  Compile failed; repair attempt {attempt}/{settings.max_repair_attempts}...")
            fixed = provider.generate_text(
                prompts.REPAIR_SYSTEM,
                prompts.repair_user(tex_path.read_text(encoding="utf-8"), result.log),
            )
            tex_source = _strip_code_fence(fixed)
            tex_path.write_text(tex_source, encoding="utf-8")
            result = compile_pdf(tex_path, work_dir)

        if not result.success or result.pdf_path is None:
            raise PipelineError(
                "LaTeX failed to compile after repair attempts.\n"
                f"Inspect the source at: {tex_path}\n"
                f"Last error log (tail):\n{result.log}"
            )

        # 8. Deliver outputs
        settings.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result.pdf_path, settings.output)
        if settings.keep_tex:
            shutil.copyfile(tex_path, settings.output.with_suffix(".tex"))
        completed = True
        log(f"Done: {settings.output}")
        return settings.output
    finally:
        # Remove only a temp dir, only on success, only if not explicitly kept.
        if is_temp and completed and not settings.keep_tex:
            shutil.rmtree(work_dir, ignore_errors=True)
        elif not completed and is_temp:
            log(f"Intermediate files kept for inspection: {work_dir}")
