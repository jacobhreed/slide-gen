"""Pydantic data contract shared between the LLM stages and the renderer.

The visual model favors *native, accurate* visuals (metric cards, data charts,
milestone lists) over AI-generated images for factual/branded content. Generated
images are restricted to abstract decoration so they can never inject the wrong
brand or garbled text. The schema stays simple (basic types, ``Literal`` enums,
no numeric/length constraints) so it works unchanged across OpenAI, Anthropic,
and Gemini structured-output APIs.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Layout = Literal[
    "title",    # opening title slide
    "section",  # section divider
    "content",  # standard content slide (bullets/body + optional visual)
    "quote",    # a highlighted quotation
    "closing",  # summary / closing
]

# What kind of visual accompanies a content slide.
VisualKind = Literal[
    "none",       # text only
    "metrics",    # a row of big-number stat cards
    "bar_chart",  # a native bar chart from real numbers
    "timeline",   # a milestone list (dates + events)
    "image",      # an abstract, decorative AI image (no text/logos/brands)
]

FontFamily = Literal["sans", "serif"]
# accent = image beside text; full = image is the slide's main element; background = subtle full-bleed
ImageStyle = Literal["accent", "full", "background"]


class StyleGuide(BaseModel):
    """Deck-wide visual design chosen by the LLM to fit the content."""

    primary_color: str = Field(description="Main brand/title color, hex like #1A2B3C")
    secondary_color: str = Field(description="Supporting color, hex")
    accent_color: str = Field(description="Accent/highlight color, hex")
    background_color: str = Field(description="Slide background, hex (usually near-white)")
    text_color: str = Field(description="Body text color, hex (high contrast on background)")
    font_family: FontFamily = Field(description="Overall typeface feel")
    visual_motif: str = Field(
        description="One sentence describing the consistent illustration style for "
        "generated images (e.g. 'clean flat infographic style with rounded shapes and "
        "the navy/teal/gold palette'), so all images look like one cohesive set."
    )
    mood: str = Field(description="A few adjectives describing the deck's mood/tone")


class Metric(BaseModel):
    """A single headline statistic for a metric-card row."""

    value: str = Field(description="The number, formatted for display, e.g. '$4.2B' or '850K'")
    label: str = Field(description="Short caption under the value, e.g. 'Deposits'")


class ChartDatum(BaseModel):
    """One bar in a bar chart."""

    label: str = Field(description="Category label, e.g. a year '2025'")
    value: float = Field(description="Numeric value for the bar")


class TimelineItem(BaseModel):
    """One milestone in a timeline."""

    date: str = Field(description="When, e.g. '2011' or 'Q3 2025'")
    label: str = Field(description="What happened, concise")


class Visual(BaseModel):
    """An optional visual for a content slide. ``kind`` selects which fields apply."""

    kind: VisualKind = Field(default="none", description="Which visual to render")
    # metrics
    metrics: list[Metric] = Field(default_factory=list, description="2-4 stat cards (kind=metrics)")
    # bar_chart
    chart_title: str = Field(default="", description="Chart caption (kind=bar_chart)")
    chart_unit: str = Field(default="", description="Y-axis unit, e.g. '$M' or '%' (kind=bar_chart)")
    chart_data: list[ChartDatum] = Field(default_factory=list, description="Bars (kind=bar_chart)")
    # timeline
    timeline: list[TimelineItem] = Field(default_factory=list, description="Milestones (kind=timeline)")
    # image (a rich, data-driven AI graphic)
    image_prompt: str = Field(
        default="",
        description="A rich, specific image-generation prompt. Describe exactly what to "
        "depict, INCLUDING the real figures/labels/relationships from this slide and the "
        "company's own brand name where relevant, plus composition and style. The pipeline "
        "adds palette and branding constraints, so focus on substance. (kind=image)",
    )
    image_facts: list[str] = Field(
        default_factory=list,
        description="The concrete facts/numbers/labels this image must depict ACCURATELY "
        "(e.g. ['2025 revenue: $236M', '2028 revenue: $388M']). Drawn only from the source. (kind=image)",
    )
    image_style: ImageStyle = Field(
        default="full",
        description="'full' (image is the slide's main element — best for data graphics), "
        "'accent' (smaller, beside text), or 'background' (subtle full-bleed)",
    )


class SlideStub(BaseModel):
    """A lightweight slide placeholder produced during planning."""

    title: str
    intent: str = Field(description="What this slide should accomplish / key message")
    section: Optional[str] = Field(default=None, description="Section this slide belongs to")


class DeckPlan(BaseModel):
    """Output of the planner stage: structure + design, before full content."""

    title: str
    subtitle: Optional[str] = None
    brand_name: Optional[str] = Field(
        default=None,
        description="The primary organization or product the deck is about, used to brand "
        "generated images. Extract it verbatim from the source.",
    )
    style: StyleGuide
    slides: list[SlideStub]


class Slide(BaseModel):
    """A fully written slide."""

    title: str
    layout: Layout = "content"
    bullets: list[str] = Field(default_factory=list, description="Bullet points (may be empty)")
    body: Optional[str] = Field(default=None, description="Optional prose/caption/quote text")
    speaker_notes: Optional[str] = Field(default=None, description="Presenter notes")
    visual: Visual = Field(default_factory=Visual)


class DeckSpec(BaseModel):
    """Output of the writer stage: the complete deck the renderer consumes."""

    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = None
    brand_name: Optional[str] = Field(
        default=None, description="Primary organization/product, used to brand generated images."
    )
    style: StyleGuide
    slides: list[Slide]
