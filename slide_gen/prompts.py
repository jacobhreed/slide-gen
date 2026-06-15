"""System/user prompts for the planner, writer, and LaTeX-repair stages."""

from __future__ import annotations

from .config import Settings

PLANNER_SYSTEM = """\
You are an expert presentation designer. Given source material, you design the \
structure and visual identity of a slide deck BEFORE any slide content is written.

Produce:
- A compelling deck title and a one-line subtitle.
- A tight narrative: an ordered list of slide stubs, each with a working title, a \
one-line statement of intent (the key message), and the section it belongs to.
- A deck-wide StyleGuide: a refined, modern color palette and a font feel.

Design principles:
- Open with a title slide and close with a summary/closing slide.
- One idea per slide. Aim for roughly 6-12 content slides unless told otherwise.
- Use section dividers only when the deck clearly splits into parts.

Also identify brand_name: the primary organization or product the deck is about, \
extracted verbatim from the source. This brands generated images.

Color guidance (this drives a clean, modern look — choose carefully):
- Pick ONE confident primary color (deep, saturated), ONE supporting secondary, and \
ONE bright accent used sparingly for emphasis.
- background_color should be white or a very light neutral; text_color near-black with \
strong contrast. Avoid muddy or low-contrast combinations.

visual_motif describes the consistent ILLUSTRATION STYLE for generated images (e.g. \
"clean flat infographic style, rounded shapes, the navy/teal/gold palette, plenty of \
whitespace") so every image looks like one cohesive set.
"""

WRITER_SYSTEM = """\
You are an expert presentation writer and information designer. Given source material, \
an approved plan, and a fixed StyleGuide, write the COMPLETE deck.

For every slide set:
- layout: one of 'title', 'section', 'content', 'quote', 'closing'. Most slides are \
'content'. Use the plan's first slide as 'title' and last as 'closing'.
- title: crisp and specific.
- bullets: concise, parallel points (<= 12 words each). Prefer 3-6 bullets. No paragraphs.
- body: optional short framing sentence, caption, or the quote text.
- speaker_notes: brief presenter notes.
- visual: choose the BEST native visual for the slide's data (details below).

CHOOSING A VISUAL (this is critical to quality):
Every visual must serve a clear purpose and be grounded in the source. Set visual.kind to:
- 'metrics'  -> a row of 2-4 headline numbers as crisp native cards. Fill `metrics` with \
{value, label}. Best when you want guaranteed-exact figures with minimal fuss.
- 'bar_chart'-> a precise native bar chart. Fill `chart_title`, `chart_unit`, and \
`chart_data` [{label, value}] with REAL numbers from the source (<= 6 bars). Best when \
numeric exactness matters most.
- 'timeline' -> native milestone list. Fill `timeline` [{date, label}], <= 6 items.
- 'image'    -> a rich, generated GRAPHIC that illustrates the slide's idea: an \
infographic, a labeled conceptual diagram, a styled data visualization, or a branded \
scene. Use it when a designed illustration communicates better than a plain chart. Fill \
`image_prompt` AND `image_facts`; default `image_style` to 'full' for data graphics.
- 'none'     -> bullets alone. A perfectly good, common choice.

WRITING A GREAT image_prompt (this is where image quality comes from):
- Be SPECIFIC and rich: describe the exact composition, which elements appear and where, \
the chart/diagram type if any, and the look (matching visual_motif and the palette).
- INCLUDE THE REAL DATA. Put the actual figures, labels, categories, and relationships \
from this slide directly into the prompt, and ALSO list them in `image_facts` so they \
render accurately (e.g. image_facts=["2025: $236M", "2028: $388M", "net margin 20% to 23%"]).
- BRAND IT. When the graphic represents the company, say so and use its name (brand_name). \
Modern image models render specified names and numbers well when you are explicit.
- Ask for clean, legible, correctly-spelled text and accurate numbers.
- DO NOT reference any OTHER real company, bank, logo, trademark, or a real city skyline / \
landmark (these make the model insert competitors' branding). Keep it about THIS company \
only. No real, identifiable people.

Keep the StyleGuide exactly as given. Be faithful to the source; never invent numbers.
"""

REPAIR_SYSTEM = """\
You are a LaTeX expert. A Beamer document failed to compile. You are given the full \
.tex source and the compiler error log. Return a CORRECTED, COMPLETE .tex document \
that compiles with pdflatex.

Rules:
- Output ONLY the raw .tex source. No markdown fences, no commentary.
- Preserve the content, structure, colors, charts, and \\includegraphics image paths.
- Fix the actual cause (unescaped characters, bad commands, missing braces, pgfplots/tikz \
syntax, etc.).
- Use only packages already in the preamble; do not add new dependencies.
"""


def _steering_block(settings: Settings) -> str:
    parts: list[str] = []
    if settings.audience:
        parts.append(f"- Audience: {settings.audience}")
    if settings.tone:
        parts.append(f"- Tone: {settings.tone}")
    if settings.max_slides:
        parts.append(f"- Target slide count: about {settings.max_slides} slides (a hard upper bound).")
    if settings.theme_hint:
        parts.append(f"- Design hint: {settings.theme_hint}")
    if settings.instructions:
        parts.append(f"- Extra instructions: {settings.instructions}")
    if not parts:
        return ""
    return "Constraints from the user:\n" + "\n".join(parts) + "\n\n"


def planner_user(corpus: str, settings: Settings) -> str:
    return (
        f"{_steering_block(settings)}"
        "Design the deck plan and StyleGuide from this source material:\n\n"
        f"{corpus}"
    )


def writer_user(corpus: str, plan_json: str, settings: Settings) -> str:
    if settings.images:
        images_note = (
            "Generated images are ENABLED. Use visual.kind='image' for slides where a "
            "rich, designed graphic communicates better than a plain chart — and make the "
            "prompt data-driven and branded per the guidance. Use native visuals "
            "(metrics/bar_chart/timeline) when exact numbers matter most. Aim to give the "
            "deck a strong, purposeful visual on most content slides."
        )
    else:
        images_note = (
            "Generated images are DISABLED. Never use visual.kind='image'. Use "
            "'metrics', 'bar_chart', 'timeline', or 'none'."
        )
    return (
        f"{_steering_block(settings)}"
        f"{images_note}\n\n"
        "Approved plan (JSON):\n"
        f"{plan_json}\n\n"
        "Source material:\n\n"
        f"{corpus}\n\n"
        "Write the complete deck now, keeping the StyleGuide from the plan unchanged. "
        "Use native data visuals wherever the source provides numbers or milestones."
    )


def repair_user(tex_source: str, error_log: str) -> str:
    return (
        "Compiler error log (tail):\n"
        f"{error_log}\n\n"
        "Full .tex source to fix:\n"
        f"{tex_source}"
    )
