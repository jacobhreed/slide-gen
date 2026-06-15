"""Render a DeckSpec into a clean, modern Beamer .tex document.

Design goals: generous whitespace, one strong accent color, flat metric cards,
native data charts (pgfplots) and timelines (TikZ) instead of fake AI diagrams,
and restrained typography. Built with plain Python string assembly so LaTeX
braces never collide with template syntax and all model text flows through one
escaping function. Targets ``pdflatex`` with common packages only.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

from ..models import DeckSpec, Slide, StyleGuide, Visual

_HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")

_FALLBACK = {
    "primary_color": "13294B",
    "secondary_color": "1F6F8B",
    "accent_color": "F2A900",
    "background_color": "FFFFFF",
    "text_color": "1A2233",
}

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_UNICODE_MAP = {
    "‘": "`", "’": "'", "“": "``", "”": "''",
    "‚": ",", "„": ",,", "′": "'", "″": "''",
    "–": "--", "—": "---", "―": "---", "−": "$-$",
    "…": r"\ldots{}", "•": r"\textbullet{} ", "●": r"\textbullet{} ",
    "·": r"\textperiodcentered{}", "⁃": r"\textbullet{} ",
    "→": r"$\rightarrow$", "←": r"$\leftarrow$",
    "↔": r"$\leftrightarrow$", "⇒": r"$\Rightarrow$", "⇐": r"$\Leftarrow$",
    "×": r"$\times$", "÷": r"$\div$", "±": r"$\pm$",
    "≈": r"$\approx$", "≤": r"$\leq$", "≥": r"$\geq$",
    "≠": r"$\neq$", "∞": r"$\infty$", "∑": r"$\sum$",
    "©": r"\textcopyright{}", "®": r"\textregistered{}",
    "™": r"\texttrademark{}", "°": r"\textdegree{}",
    "€": r"\texteuro{}", "£": r"\pounds{}", "¥": r"\textyen{}",
    "¢": r"\textcent{}", "§": r"\S{}", "¶": r"\P{}",
    "½": r"$\frac{1}{2}$", "¼": r"$\frac{1}{4}$", "¾": r"$\frac{3}{4}$",
    "✓": r"$\checkmark$", "✔": r"$\checkmark$", "✗": r"$\times$",
    "✘": r"$\times$",
    " ": "~",   # non-breaking space
    " ": "~",   # figure space
    " ": "~",   # narrow no-break space
    " ": r"\,",  # thin space
    "​": "",    # zero-width space
    "﻿": "",    # BOM / zero-width no-break space
}

_LATIN_LETTER_MAX = 0x017F


def _fold_to_ascii(ch: str) -> str:
    folded = unicodedata.normalize("NFKD", ch)
    ascii_part = "".join(
        c for c in folded if ord(c) < 128 and not unicodedata.combining(c)
    )
    return "".join(_LATEX_SPECIALS.get(c, c) for c in ascii_part)


def latex_escape(text: Optional[str]) -> str:
    """Escape a string for safe inclusion in LaTeX body text (pdflatex-safe)."""
    if not text:
        return ""
    out: list[str] = []
    for ch in text:
        if ch in _UNICODE_MAP:
            out.append(_UNICODE_MAP[ch])
        elif ch in _LATEX_SPECIALS:
            out.append(_LATEX_SPECIALS[ch])
        elif ord(ch) < 128:
            out.append(ch)
        elif unicodedata.category(ch).startswith("L") and ord(ch) <= _LATIN_LETTER_MAX:
            out.append(ch)
        else:
            out.append(_fold_to_ascii(ch))
    return "".join(out)


def _hex(value: str, fallback_key: str) -> str:
    cleaned = (value or "").lstrip("#").strip()
    if _HEX_RE.match(cleaned):
        return cleaned.upper()
    return _FALLBACK[fallback_key]


def _clean_number(value: float) -> str:
    """Render a float without a trailing .0, for pgfplots coordinates."""
    if value == int(value):
        return str(int(value))
    return repr(value)


# --------------------------------------------------------------------------- #
# Preamble — a flat, modern theme built on Beamer's default with custom colors.
# --------------------------------------------------------------------------- #
def _preamble(style: StyleGuide) -> str:
    primary = _hex(style.primary_color, "primary_color")
    secondary = _hex(style.secondary_color, "secondary_color")
    accent = _hex(style.accent_color, "accent_color")
    background = _hex(style.background_color, "background_color")
    text = _hex(style.text_color, "text_color")
    family = r"\sfdefault" if style.font_family == "sans" else r"\rmdefault"

    return rf"""\documentclass[aspectratio=169,11pt]{{beamer}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage{{textcomp}}
\usepackage{{amssymb}}
\usepackage{{graphicx}}
\usepackage{{xcolor}}
\usepackage{{ragged2e}}
\usepackage{{tikz}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.16}}
\usetikzlibrary{{calc}}

\usetheme{{default}}
\useinnertheme{{default}}
\useoutertheme{{default}}
\setbeamertemplate{{navigation symbols}}{{}}
\renewcommand{{\familydefault}}{{{family}}}

\definecolor{{deckprimary}}{{HTML}}{{{primary}}}
\definecolor{{decksecondary}}{{HTML}}{{{secondary}}}
\definecolor{{deckaccent}}{{HTML}}{{{accent}}}
\definecolor{{deckbg}}{{HTML}}{{{background}}}
\definecolor{{decktext}}{{HTML}}{{{text}}}
\definecolor{{deckmuted}}{{HTML}}{{8A94A6}}
\definecolor{{deckcard}}{{HTML}}{{EEF2F7}}

\setbeamercolor{{background canvas}}{{bg=deckbg}}
\setbeamercolor{{normal text}}{{fg=decktext}}
\setbeamercolor{{structure}}{{fg=deckprimary}}
\setbeamercolor{{frametitle}}{{fg=deckprimary,bg=deckbg}}
\setbeamercolor{{title}}{{fg=deckprimary}}
\setbeamercolor{{itemize item}}{{fg=deckaccent}}
\setbeamercolor{{itemize subitem}}{{fg=decksecondary}}

\setbeamerfont{{frametitle}}{{series=\bfseries,size=\Large}}
\setbeamerfont{{title}}{{series=\bfseries,size=\fontsize{{30}}{{34}}\selectfont}}
\setbeamerfont{{itemize/enumerate body}}{{size=\large}}
\setbeamertemplate{{itemize item}}{{\small\raisebox{{0.18ex}}{{\textbullet}}}}
\setbeamertemplate{{itemize subitem}}{{\textendash}}

% Flat frame title with an accent rule underneath, ample top margin.
\setbeamertemplate{{frametitle}}{{%
  \vspace*{{0.6em}}%
  \begin{{beamercolorbox}}[wd=\paperwidth,leftskip=0.9cm,rightskip=0.9cm]{{frametitle}}%
    \usebeamerfont{{frametitle}}\insertframetitle\par%
    \vspace{{0.25em}}%
    {{\color{{deckaccent}}\rule{{2.2cm}}{{2.2pt}}}}%
  \end{{beamercolorbox}}%
  \vspace{{0.4em}}%
}}

\setbeamertemplate{{itemize/enumerate body begin}}{{\setlength{{\itemsep}}{{0.5em}}}}

% Tighter default plot styling.
\pgfplotsset{{
  deckbar/.style={{
    width=\textwidth, height=5.2cm,
    ybar, bar width=0.7cm,
    ymin=0, axis lines=left,
    axis line style={{deckmuted}},
    tick style={{deckmuted}},
    xtick=data, enlarge x limits=0.18,
    ymajorgrids, grid style={{deckcard}},
    every node near coord/.append style={{font=\small\bfseries,color=deckprimary}},
    label style={{font=\small,color=deckmuted}},
    tick label style={{font=\small,color=decktext}},
  }},
}}
"""


# --------------------------------------------------------------------------- #
# Slide pieces
# --------------------------------------------------------------------------- #
def _title_page(deck: DeckSpec) -> str:
    sub = latex_escape(deck.subtitle) if deck.subtitle else ""
    author = latex_escape(deck.author) if deck.author else ""
    lines = [
        r"\begin{frame}[plain]",
        r"  \begin{tikzpicture}[remember picture,overlay]",
        r"    \fill[deckaccent] (current page.north west) rectangle "
        r"([yshift=-0.35cm]current page.north east);",
        r"  \end{tikzpicture}",
        r"  \vfill",
        r"  \begingroup\raggedright",
        rf"  {{\usebeamerfont{{title}}\color{{deckprimary}} {latex_escape(deck.title)}\par}}",
    ]
    if sub:
        lines.append(r"  \vspace{0.6em}")
        lines.append(rf"  {{\Large\color{{decksecondary}} {sub}\par}}")
    if author:
        lines.append(r"  \vspace{1.4em}")
        lines.append(rf"  {{\normalsize\color{{deckmuted}} {author}\par}}")
    lines += [r"  \endgroup", r"  \vfill", r"\end{frame}"]
    return "\n".join(lines)


def _render_section(slide: Slide) -> str:
    lines = [
        r"\begin{frame}[plain]",
        r"  \centering\vfill",
        rf"  {{\usebeamercolor[fg]{{structure}}\Huge\bfseries {latex_escape(slide.title)}\par}}",
    ]
    if slide.body and slide.body.strip():
        lines += [
            r"  \vspace{0.8em}",
            rf"  {{\large\color{{decksecondary}} {latex_escape(slide.body)}\par}}",
        ]
    lines += [
        r"  \vspace{0.6em}",
        r"  {\color{deckaccent}\rule{3cm}{2.5pt}}",
        r"  \vfill",
        r"\end{frame}",
    ]
    return "\n".join(lines)


def _render_quote(slide: Slide) -> str:
    quote = latex_escape(slide.body or " ".join(slide.bullets))
    lines = [
        r"\begin{frame}[plain]",
        r"  \centering\vfill",
        r"  \begin{minipage}{0.82\textwidth}\centering",
        rf"  {{\color{{deckaccent}}\fontsize{{40}}{{40}}\selectfont ``}}\par\vspace{{-0.3em}}",
        rf"  {{\LARGE\itshape\color{{decktext}} {quote}}}\par",
    ]
    if slide.title and slide.title.strip():
        lines += [
            r"  \vspace{1.2em}",
            rf"  {{\large\bfseries\color{{decksecondary}} {latex_escape(slide.title)}\par}}",
        ]
    lines += [r"  \end{minipage}", r"  \vfill", r"\end{frame}"]
    return "\n".join(lines)


def _itemize(bullets: list[str]) -> str:
    items = [rf"    \item {latex_escape(b)}" for b in bullets if b and b.strip()]
    if not items:
        return ""
    return "  \\begin{itemize}\n" + "\n".join(items) + "\n  \\end{itemize}"


def _metric_cards(visual: Visual) -> str:
    cards = visual.metrics[:4]
    if not cards:
        return ""
    width = {1: "0.6", 2: "0.42", 3: "0.3", 4: "0.22"}[len(cards)]
    boxes = []
    for m in cards:
        boxes.append(
            "\n".join(
                [
                    rf"  \begin{{minipage}}[t]{{{width}\textwidth}}",
                    r"    \begin{beamercolorbox}[wd=\textwidth,sep=10pt,rounded=true]{normal text}",
                    r"      \centering\colorbox{deckcard}{\parbox[t][2.4cm][c]{\dimexpr\textwidth-20pt\relax}{%",
                    rf"        \centering{{\color{{deckprimary}}\fontsize{{26}}{{28}}\selectfont\bfseries {latex_escape(m.value)}}}\par",
                    rf"        \vspace{{0.3em}}{{\small\color{{deckmuted}} {latex_escape(m.label)}}}\par}}}}",
                    r"    \end{beamercolorbox}",
                    r"  \end{minipage}",
                ]
            )
        )
    return "  \\begin{center}\n" + "\\hfill\n".join(boxes) + "\n  \\end{center}"


def _bar_chart(visual: Visual) -> str:
    data = [d for d in visual.chart_data if d.label]
    if not data:
        return ""
    coords = " ".join(f"({latex_escape(d.label)},{_clean_number(d.value)})" for d in data)
    symbolic = ",".join(latex_escape(d.label) for d in data)
    ylabel = rf"ylabel={{{latex_escape(visual.chart_unit)}}}," if visual.chart_unit else ""
    title = ""
    if visual.chart_title:
        title = rf"  {{\small\bfseries\color{{deckprimary}} {latex_escape(visual.chart_title)}}}\par\vspace{{0.3em}}" + "\n"
    return (
        "  \\begin{center}\n"
        + title
        + "  \\begin{tikzpicture}\n"
        + "  \\begin{axis}[deckbar,\n"
        + f"    symbolic x coords={{{symbolic}}},\n"
        + f"    {ylabel}\n"
        + "    nodes near coords,\n"
        + "  ]\n"
        + f"  \\addplot[fill=deckaccent,draw=none] coordinates {{{coords}}};\n"
        + "  \\end{axis}\n  \\end{tikzpicture}\n  \\end{center}"
    )


def _timeline(visual: Visual) -> str:
    items = [t for t in visual.timeline if t.date or t.label][:6]
    if not items:
        return ""
    rows = []
    for t in items:
        rows.append(
            r"  \item {\bfseries\color{deckprimary} "
            rf"{latex_escape(t.date)}}}\;\textemdash\; {latex_escape(t.label)}"
        )
    return "  \\begin{itemize}\n" + "\n".join(rows) + "\n  \\end{itemize}"


def _image_box(image_path: Path, width: str) -> str:
    path = Path(image_path).resolve().as_posix()
    return rf"\includegraphics[width={width},height=0.72\textheight,keepaspectratio]{{{path}}}"


def _text_block(slide: Slide) -> list[str]:
    parts: list[str] = []
    if slide.body and slide.body.strip():
        parts.append(rf"  {{\justifying {latex_escape(slide.body)}\par}}")
        parts.append(r"  \vspace{0.5em}")
    bullets = _itemize(slide.bullets)
    if bullets:
        parts.append(bullets)
    return parts


def _native_visual(visual: Visual) -> str:
    """Render a non-image visual (metrics/chart/timeline) to LaTeX, else ''."""
    if visual.kind == "metrics":
        return _metric_cards(visual)
    if visual.kind == "bar_chart":
        return _bar_chart(visual)
    if visual.kind == "timeline":
        return _timeline(visual)
    return ""


def _render_content(slide: Slide, image_path: Optional[Path]) -> str:
    visual = slide.visual
    parts = [rf"\begin{{frame}}{{{latex_escape(slide.title)}}}"]

    # Generated image. 'full' = image is the main element (best for data graphics),
    # 'accent' = smaller image beside text, 'background' = subtle full-bleed.
    if visual.kind == "image" and image_path is not None:
        if visual.image_style == "background":
            path = Path(image_path).resolve().as_posix()
            parts.insert(
                1,
                "\n".join(
                    [
                        r"  \begin{tikzpicture}[remember picture,overlay]",
                        rf"    \node[opacity=0.10,inner sep=0] at (current page.center) "
                        rf"{{\includegraphics[width=\paperwidth,height=\paperheight]{{{path}}}}};",
                        r"  \end{tikzpicture}",
                    ]
                ),
            )
            parts += _text_block(slide)
        elif visual.image_style == "accent":
            text = "\n".join(_text_block(slide)).rstrip()
            parts += [
                r"  \begin{columns}[T]",
                r"    \begin{column}{0.56\textwidth}",
                text,
                r"    \end{column}",
                r"    \begin{column}{0.40\textwidth}\centering",
                "      " + _image_box(image_path, r"\linewidth"),
                r"    \end{column}",
                r"  \end{columns}",
            ]
        else:  # 'full' — the image carries the slide; only a short caption (body).
            parts.append(r"  \centering")
            if slide.body and slide.body.strip():
                parts.append(rf"  {{\small\color{{deckmuted}} {latex_escape(slide.body)}\par}}")
                parts.append(r"  \vspace{0.3em}")
            parts.append("  " + _image_box(image_path, r"\linewidth"))
        parts.append(r"\end{frame}")
        return "\n".join(parts)

    # Native visual (metrics/chart/timeline): text on top, visual below.
    native = _native_visual(visual)
    parts += _text_block(slide)
    if native:
        parts.append(r"  \vspace{0.4em}")
        parts.append(native)
    parts.append(r"\end{frame}")
    return "\n".join(parts)


def _render_slide(slide: Slide, image_path: Optional[Path]) -> str:
    if slide.layout == "section":
        return _render_section(slide)
    if slide.layout == "quote":
        return _render_quote(slide)
    # title is handled by the dedicated title page; treat stray 'title' as content.
    return _render_content(slide, image_path)


def render_latex(deck: DeckSpec, images: Optional[dict[int, Path]] = None) -> str:
    """Render the full .tex document.

    ``images`` maps a slide's index to a generated PNG path; only slides whose
    ``visual.kind == 'image'`` use it.
    """
    images = images or {}
    body_parts = [_title_page(deck)]
    for idx, slide in enumerate(deck.slides):
        image_path = images.get(idx)
        if slide.visual.kind != "image":
            image_path = None
        body_parts.append(_render_slide(slide, image_path))

    return "\n\n".join(
        [
            _preamble(deck.style),
            r"\begin{document}",
            *body_parts,
            r"\end{document}",
            "",
        ]
    )
