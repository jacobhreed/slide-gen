"""Pipeline orchestration tests with mocked providers and a mocked LaTeX compile."""

from pathlib import Path

from slide_gen import pipeline
from slide_gen.config import Settings
from slide_gen.models import DeckPlan, DeckSpec, Slide, StyleGuide, Visual
from slide_gen.render.compile import CompileResult


def _style(primary="#111111") -> StyleGuide:
    return StyleGuide(
        primary_color=primary,
        secondary_color="#222222",
        accent_color="#333333",
        background_color="#FFFFFF",
        text_color="#000000",
        font_family="sans",
        visual_motif="motif",
        mood="calm",
    )


class FakeProvider:
    """Returns canned structured output; records call counts."""

    def __init__(self):
        self.text_calls = 0
        self.structured_calls = 0

    def generate_structured(self, system, user, schema):
        self.structured_calls += 1
        if schema is DeckPlan:
            # brand_name lives on the plan; the pipeline backfills it onto the deck.
            return DeckPlan(title="Planned Title", subtitle="Sub", brand_name="Acme Corp",
                            style=_style("#ABCDEF"), slides=[])
        if schema is DeckSpec:
            # Note: writer returns a DIFFERENT style and no brand; pipeline must
            # overwrite the style and backfill brand_name from the plan.
            return DeckSpec(
                title="",  # empty -> pipeline backfills from plan
                style=_style("#000000"),
                slides=[
                    Slide(title="One", layout="content", bullets=["a", "b"]),
                    Slide(
                        title="Visual",
                        layout="content",
                        bullets=["fact one"],
                        visual=Visual(kind="image", image_prompt="abstract gradient",
                                      image_style="full"),
                    ),
                ],
            )
        raise AssertionError("unexpected schema")

    def generate_text(self, system, user):
        self.text_calls += 1
        return "```latex\n\\documentclass{beamer}\\begin{document}\\end{document}\n```"


class FakeImage:
    def __init__(self):
        self.calls = 0
        self.prompts = []

    def generate(self, prompt, size):
        self.calls += 1
        self.prompts.append(prompt)
        return b"\x89PNG\r\n\x1a\n-fake-"


def _ok_compile(tex_path, work_dir):
    pdf = work_dir / "deck.pdf"
    pdf.write_bytes(b"%PDF-1.5\n%%EOF\n")
    return CompileResult(True, pdf, "ok")


def _settings(tmp_path: Path, **overrides) -> Settings:
    src = tmp_path / "in.txt"
    src.write_text("some source material", encoding="utf-8")
    base = dict(inputs=[src], output=tmp_path / "out.pdf", work_dir=tmp_path / "work")
    base.update(overrides)
    return Settings(**base)


def test_pipeline_success_first_compile(tmp_path, monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)

    def fake_compile(tex_path: Path, work_dir: Path) -> CompileResult:
        pdf = work_dir / "deck.pdf"
        pdf.write_bytes(b"%PDF-1.5\n%%EOF\n")
        return CompileResult(True, pdf, "ok")

    monkeypatch.setattr(pipeline, "compile_pdf", fake_compile)

    out = pipeline.generate_deck(_settings(tmp_path, keep_tex=True))
    assert out.exists()
    # Plan's style and title were enforced onto the deck -> visible in the .tex.
    tex = out.with_suffix(".tex").read_text(encoding="utf-8")
    assert "ABCDEF" in tex
    assert "Planned Title" in tex
    assert provider.text_calls == 0  # no repair needed


def test_pipeline_repair_loop_recovers(tmp_path, monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)

    state = {"calls": 0}

    def flaky_compile(tex_path: Path, work_dir: Path) -> CompileResult:
        state["calls"] += 1
        if state["calls"] == 1:
            return CompileResult(False, None, "! Undefined control sequence.")
        pdf = work_dir / "deck.pdf"
        pdf.write_bytes(b"%PDF-1.5\n%%EOF\n")
        return CompileResult(True, pdf, "ok")

    monkeypatch.setattr(pipeline, "compile_pdf", flaky_compile)

    out = pipeline.generate_deck(_settings(tmp_path))
    assert out.exists()
    assert provider.text_calls == 1  # one repair attempt was made


def test_pipeline_raises_when_unrepairable(tmp_path, monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)
    monkeypatch.setattr(
        pipeline, "compile_pdf",
        lambda tex_path, work_dir: CompileResult(False, None, "fatal error"),
    )

    import pytest

    with pytest.raises(pipeline.PipelineError):
        pipeline.generate_deck(_settings(tmp_path, max_repair_attempts=1))


def test_engine_error_skips_repair(tmp_path, monkeypatch):
    import pytest

    provider = FakeProvider()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)
    monkeypatch.setattr(
        pipeline, "compile_pdf",
        lambda tex_path, work_dir: CompileResult(False, None, "no perl", engine_error=True),
    )

    with pytest.raises(pipeline.PipelineError) as excinfo:
        pipeline.generate_deck(_settings(tmp_path))
    assert provider.text_calls == 0  # no wasted repair calls on a toolchain error
    assert "toolchain" in str(excinfo.value).lower()


def test_resume_reuses_plan_and_deck(tmp_path, monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)
    monkeypatch.setattr(pipeline, "compile_pdf", _ok_compile)

    settings = _settings(tmp_path, resume=True)  # persistent work_dir, cache reads on

    pipeline.generate_deck(settings)
    assert provider.structured_calls == 2  # plan + deck
    assert (settings.work_dir / "plan.json").exists()
    assert (settings.work_dir / "deck.json").exists()

    # Second run resumes: no new structured LLM calls.
    pipeline.generate_deck(settings)
    assert provider.structured_calls == 2


def test_resume_regenerates_incompatible_cache(tmp_path, monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)
    monkeypatch.setattr(pipeline, "compile_pdf", _ok_compile)

    settings = _settings(tmp_path, resume=True)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    # Simulate an old-schema cache file that no longer validates.
    (settings.work_dir / "plan.json").write_text(
        '{"layout": "two_column", "obsolete": true}', encoding="utf-8"
    )

    # Should not raise; regenerates plan + deck instead of crashing.
    out = pipeline.generate_deck(settings)
    assert out.exists()
    assert provider.structured_calls == 2


def test_resume_reuses_cached_images(tmp_path, monkeypatch):
    provider = FakeProvider()
    image = FakeImage()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)
    monkeypatch.setattr(pipeline, "get_image_provider", lambda *a, **k: image)
    monkeypatch.setattr(pipeline, "compile_pdf", _ok_compile)

    settings = _settings(tmp_path, resume=True, images=True)

    pipeline.generate_deck(settings)
    assert image.calls == 1  # one generated_image slide
    imgs = list((settings.work_dir / "images").glob("*.png"))
    assert len(imgs) == 1

    # Resume: the cached PNG is reused, no new image API call.
    pipeline.generate_deck(settings)
    assert image.calls == 1


def test_image_prompts_are_rich_branded_and_data_driven(tmp_path, monkeypatch):
    provider = FakeProvider()
    image = FakeImage()
    monkeypatch.setattr(pipeline, "get_assembly_provider", lambda *a, **k: provider)
    monkeypatch.setattr(pipeline, "get_image_provider", lambda *a, **k: image)
    monkeypatch.setattr(pipeline, "compile_pdf", _ok_compile)

    pipeline.generate_deck(_settings(tmp_path, images=True))
    assert image.prompts, "expected an image request"
    sent = image.prompts[0]
    low = sent.lower()
    # The writer's creative direction is preserved...
    assert "abstract gradient" in low
    # ...the brand from the plan is injected (not hardcoded anywhere)...
    assert "Acme Corp" in sent
    # ...the slide's real facts are fed in for accurate rendering...
    assert "fact one" in low
    # ...the palette is passed through...
    assert "#abcdef" in low
    # ...and the smart guardrail forbids OTHER brands while allowing this one.
    assert "do not include any other real company" in low
    assert "legible" in low


def test_build_image_prompt_includes_structured_facts(tmp_path):
    from slide_gen.models import ChartDatum, Metric, StyleGuide, TimelineItem, Visual

    deck = DeckSpec(
        title="D", brand_name="Acme Corp",
        style=StyleGuide(
            primary_color="#0B2D4D", secondary_color="#1F6F8B", accent_color="#F2A900",
            background_color="#FFFFFF", text_color="#14213D", font_family="sans",
            visual_motif="flat infographic", mood="modern",
        ),
        slides=[Slide(
            title="Outlook", layout="content",
            visual=Visual(
                kind="image", image_prompt="a revenue growth infographic",
                image_facts=["2025: $236M"],
                chart_data=[ChartDatum(label="2028", value=388)],
                timeline=[TimelineItem(date="2026", label="Launch")],
                metrics=[Metric(value="23%", label="margin")],
            ),
            bullets=["Strong momentum"],
        )],
    )
    prompt = pipeline._build_image_prompt(deck, deck.slides[0])
    for needle in ["a revenue growth infographic", "2025: $236M", "388 (2028)",
                   "2026: Launch", "23% margin", "Strong momentum", "Acme Corp"]:
        assert needle in prompt, needle
