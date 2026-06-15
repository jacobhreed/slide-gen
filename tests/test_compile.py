import pytest

import slide_gen.render.compile as cmod


def test_no_engine_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(cmod.shutil, "which", lambda name: None)
    tex = tmp_path / "deck.tex"
    tex.write_text("dummy", encoding="utf-8")
    with pytest.raises(cmod.LatexNotFoundError):
        cmod.compile_pdf(tex, tmp_path)


def test_falls_back_from_latexmk_to_pdflatex(monkeypatch, tmp_path):
    # Both engines "exist" on PATH.
    monkeypatch.setattr(cmod.shutil, "which", lambda name: f"/usr/bin/{name}")

    tex = tmp_path / "deck.tex"
    tex.write_text("dummy", encoding="utf-8")
    calls = []

    def fake_run(cmd, **kwargs):
        engine = cmd[0]
        calls.append(engine)

        class Proc:
            stdout = ""
            stderr = ""

        if engine == "latexmk":
            # latexmk fails without writing a LaTeX log (the MiKTeX/Perl case).
            Proc.stderr = "could not find the script engine 'perl'"
            return Proc()
        # pdflatex runs: writes a log and a pdf.
        (tmp_path / "deck.log").write_text("This is pdfTeX ... no errors", encoding="utf-8")
        (tmp_path / "deck.pdf").write_bytes(b"%PDF-1.5\n%%EOF\n")
        return Proc()

    monkeypatch.setattr(cmod.subprocess, "run", fake_run)
    result = cmod.compile_pdf(tex, tmp_path)
    assert result.success is True
    assert "latexmk" in calls and "pdflatex" in calls  # fell back


def test_engine_error_when_nothing_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(cmod.shutil, "which", lambda name: "/usr/bin/latexmk" if name == "latexmk" else None)
    tex = tmp_path / "deck.tex"
    tex.write_text("dummy", encoding="utf-8")

    class Proc:
        stdout = ""
        stderr = "could not find the script engine 'perl'"

    monkeypatch.setattr(cmod.subprocess, "run", lambda cmd, **k: Proc())
    result = cmod.compile_pdf(tex, tmp_path)
    assert result.success is False
    assert result.engine_error is True  # no LaTeX log -> toolchain problem
