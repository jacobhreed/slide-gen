"""Compile a Beamer .tex file to PDF, detecting the available LaTeX engine.

Prefers ``latexmk`` but automatically falls back to ``pdflatex`` if latexmk
cannot run (a common case on MiKTeX installs without Perl). Distinguishes a
*toolchain* failure (no engine could run) from a *content* failure (LaTeX ran
and the source had errors) so the caller doesn't waste an LLM repair pass on a
broken install.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class LatexNotFoundError(Exception):
    """Raised when no LaTeX toolchain is installed at all."""


@dataclass
class CompileResult:
    success: bool
    pdf_path: Optional[Path]
    log: str
    engine_error: bool = False  # True when no engine could run (vs. a source error)


def find_latex_engine() -> tuple[str, bool]:
    """Return (engine, is_latexmk). Prefer latexmk; fall back to pdflatex.

    Raises LatexNotFoundError if neither is on PATH.
    """
    if shutil.which("latexmk"):
        return "latexmk", True
    if shutil.which("pdflatex"):
        return "pdflatex", False
    raise LatexNotFoundError(
        "No LaTeX toolchain found. Install TeX Live or MiKTeX so that 'pdflatex' "
        "(and ideally 'latexmk') is on your PATH."
    )


def _tail(text: str, lines: int = 60) -> str:
    return "\n".join(text.splitlines()[-lines:])


def _commands_for(engine: str, tex_path: Path, work_dir: Path) -> list[list[str]]:
    out = f"-output-directory={work_dir}"
    if engine == "latexmk":
        return [["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", out, str(tex_path)]]
    # Two pdflatex passes so the title page / refs settle.
    single = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", out, str(tex_path)]
    return [single, single]


def compile_pdf(tex_path: Path, work_dir: Path) -> CompileResult:
    """Compile ``tex_path`` inside ``work_dir`` and return the result.

    Tries latexmk first, then pdflatex. A failed compile never raises (except a
    completely missing toolchain): it returns ``success=False`` with the log so
    the caller can decide whether to run the repair loop (content error) or stop
    (``engine_error`` — the engine itself could not run).
    """
    # Absolute paths so the compile is independent of the process CWD (we run with
    # cwd=work_dir, and embedded image paths are absolute too).
    work_dir = work_dir.resolve()
    tex_path = tex_path.resolve()
    stem = tex_path.stem
    log_file = work_dir / f"{stem}.log"
    pdf_path = work_dir / f"{stem}.pdf"

    engines: list[str] = []
    if shutil.which("latexmk"):
        engines.append("latexmk")
    if shutil.which("pdflatex"):
        engines.append("pdflatex")
    if not engines:
        raise LatexNotFoundError(
            "No LaTeX toolchain found. Install TeX Live or MiKTeX so that "
            "'pdflatex' is on your PATH."
        )

    combined = ""
    for engine in engines:
        # Clear a stale log so its presence reliably signals "LaTeX actually ran".
        if log_file.exists():
            try:
                log_file.unlink()
            except OSError:
                pass

        for cmd in _commands_for(engine, tex_path, work_dir):
            try:
                proc = subprocess.run(
                    cmd, cwd=str(work_dir), capture_output=True, text=True, timeout=180
                )
            except FileNotFoundError:
                combined += f"\n[{engine}] executable not found.\n"
                break
            except subprocess.TimeoutExpired as exc:
                return CompileResult(False, None, f"LaTeX timed out: {exc}")
            combined += proc.stdout + proc.stderr + "\n"

        if pdf_path.exists():
            tail = log_file.read_text(encoding="utf-8", errors="replace") if log_file.exists() else combined
            return CompileResult(True, pdf_path, _tail(tail), engine_error=False)

        if log_file.exists():
            # LaTeX ran but produced no PDF -> a real source error. The repair
            # loop can help; no point trying another engine on the same source.
            return CompileResult(
                False, None, _tail(log_file.read_text(encoding="utf-8", errors="replace")),
                engine_error=False,
            )
        # No PDF and no LaTeX log -> this engine could not run; try the next one.

    # No engine managed to run LaTeX at all.
    return CompileResult(False, None, _tail(combined), engine_error=True)
