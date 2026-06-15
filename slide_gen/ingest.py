"""Read source documents (txt, md, pdf, docx) and folders into one text corpus."""

from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".text"}
PDF_SUFFIXES = {".pdf"}
DOCX_SUFFIXES = {".docx"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | PDF_SUFFIXES | DOCX_SUFFIXES


class IngestError(Exception):
    """Raised when an input cannot be read."""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - import guard
        raise IngestError("Reading PDF requires 'pypdf' (pip install pypdf).") from exc

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n\n".join(pages).strip()


def _read_docx(path: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover - import guard
        raise IngestError("Reading .docx requires 'python-docx' (pip install python-docx).") from exc

    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs).strip()


def read_one(path: Path) -> str:
    """Read a single file based on its suffix."""
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return _read_text(path)
    if suffix in PDF_SUFFIXES:
        return _read_pdf(path)
    if suffix in DOCX_SUFFIXES:
        return _read_docx(path)
    raise IngestError(
        f"Unsupported file type '{suffix}' for {path.name}. "
        f"Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}."
    )


def expand_inputs(paths: list[Path]) -> list[Path]:
    """Expand directories into their supported files; keep files as-is.

    Files are returned in a stable, sorted order so output is deterministic.
    """
    resolved: list[Path] = []
    for path in paths:
        if not path.exists():
            raise IngestError(f"Input not found: {path}")
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
                    resolved.append(child)
        else:
            resolved.append(path)
    if not resolved:
        raise IngestError("No readable input files found.")
    return resolved


def build_corpus(paths: list[Path]) -> str:
    """Read all inputs and concatenate into one labeled corpus string."""
    files = expand_inputs(paths)
    chunks: list[str] = []
    for path in files:
        content = read_one(path).strip()
        if not content:
            continue
        chunks.append(f"===== SOURCE: {path.name} =====\n{content}")
    if not chunks:
        raise IngestError("All inputs were empty after reading.")
    return "\n\n".join(chunks)
