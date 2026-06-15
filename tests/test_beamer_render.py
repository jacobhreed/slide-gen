from slide_gen.models import (
    ChartDatum,
    DeckSpec,
    Metric,
    Slide,
    StyleGuide,
    TimelineItem,
    Visual,
)
from slide_gen.render.beamer import latex_escape, render_latex


def _style() -> StyleGuide:
    return StyleGuide(
        primary_color="#0B2D4D",
        secondary_color="#1F6F8B",
        accent_color="#F2A900",
        background_color="#FFFFFF",
        text_color="#14213D",
        font_family="sans",
        visual_motif="abstract soft gradients and geometric shapes",
        mood="confident, modern",
    )


def test_latex_escape_specials():
    assert latex_escape("Profit & Loss 50% _x_ #1") == r"Profit \& Loss 50\% \_x\_ \#1"
    assert latex_escape(None) == ""


def test_latex_escape_unicode_punctuation_and_symbols():
    assert latex_escape("“Hi”") == "``Hi''"
    assert latex_escape("a—b") == "a---b"
    assert latex_escape("a–b") == "a--b"
    assert latex_escape("etc…") == r"etc\ldots{}"
    assert latex_escape("5€") == r"5\texteuro{}"
    assert latex_escape("x→y") == r"x$\rightarrow$y"
    assert latex_escape("≥90%") == r"$\geq$90\%"
    assert latex_escape("Muñoz café") == "Muñoz café"
    assert latex_escape("great \U0001F600 news") == "great  news"


def test_preamble_loads_required_packages():
    deck = DeckSpec(title="D", style=_style(), slides=[Slide(title="s", layout="content")])
    tex = render_latex(deck)
    for pkg in (r"\usepackage{textcomp}", r"\usepackage{amssymb}",
                r"\usepackage{pgfplots}", r"\usepackage{tikz}"):
        assert pkg in tex
    assert r"\definecolor{deckprimary}{HTML}{0B2D4D}" in tex


def test_basic_document_structure_and_escaping():
    deck = DeckSpec(
        title="Q3 & Beyond",
        subtitle="A 50% jump",
        style=_style(),
        slides=[
            Slide(title="Intro", layout="content", bullets=["First point", "Second & third"]),
            Slide(title="A Quote", layout="quote", body="Stay hungry"),
        ],
    )
    tex = render_latex(deck)
    assert r"\begin{document}" in tex and r"\end{document}" in tex
    assert r"Q3 \& Beyond" in tex
    assert r"Second \& third" in tex
    assert r"\includegraphics" not in tex  # no image requested


def test_metrics_visual_renders_cards():
    deck = DeckSpec(
        title="D", style=_style(),
        slides=[Slide(
            title="By the numbers", layout="content",
            visual=Visual(kind="metrics", metrics=[
                Metric(value="$4.2B", label="Deposits"),
                Metric(value="850K", label="Customers"),
            ]),
        )],
    )
    tex = render_latex(deck)
    assert r"\$4.2B" in tex
    assert "Deposits" in tex and "Customers" in tex
    assert r"\includegraphics" not in tex  # native, not an image


def test_bar_chart_uses_pgfplots_with_real_numbers():
    deck = DeckSpec(
        title="D", style=_style(),
        slides=[Slide(
            title="Revenue", layout="content",
            visual=Visual(kind="bar_chart", chart_title="Revenue", chart_unit="$M",
                          chart_data=[ChartDatum(label="2025", value=236),
                                      ChartDatum(label="2026", value=290.5)]),
        )],
    )
    tex = render_latex(deck)
    assert r"\begin{axis}" in tex and r"\addplot" in tex
    assert "(2025,236)" in tex
    assert "(2026,290.5)" in tex
    assert "symbolic x coords={2025,2026}" in tex


def test_timeline_visual():
    deck = DeckSpec(
        title="D", style=_style(),
        slides=[Slide(
            title="History", layout="content",
            visual=Visual(kind="timeline", timeline=[
                TimelineItem(date="2011", label="Founded"),
                TimelineItem(date="2026", label="Launch"),
            ]),
        )],
    )
    tex = render_latex(deck)
    assert "2011" in tex and "Founded" in tex
    assert "2026" in tex and "Launch" in tex


def test_image_visual_two_column(tmp_path):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n")
    deck = DeckSpec(
        title="D", style=_style(),
        slides=[Slide(
            title="Accent", layout="content", bullets=["a point"],
            visual=Visual(kind="image", image_prompt="abstract gradient", image_style="accent"),
        )],
    )
    tex = render_latex(deck, images={0: img})
    assert r"\begin{columns}" in tex
    assert r"\includegraphics" in tex
    assert "pic.png" in tex.replace("\\", "/")


def test_image_ignored_when_kind_not_image(tmp_path):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n")
    deck = DeckSpec(
        title="D", style=_style(),
        slides=[Slide(title="No image", layout="content", bullets=["x"])],
    )
    tex = render_latex(deck, images={0: img})
    assert r"\includegraphics" not in tex


def test_invalid_color_falls_back():
    style = _style()
    style.primary_color = "not-a-color"
    deck = DeckSpec(title="D", style=style, slides=[Slide(title="s", layout="content")])
    tex = render_latex(deck)
    assert r"\definecolor{deckprimary}{HTML}{13294B}" in tex  # fallback value
