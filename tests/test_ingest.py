from pathlib import Path

import pytest

from slide_gen.ingest import IngestError, build_corpus, expand_inputs


def test_reads_text_and_markdown(tmp_path: Path):
    (tmp_path / "a.txt").write_text("alpha content", encoding="utf-8")
    (tmp_path / "b.md").write_text("# beta\nbeta content", encoding="utf-8")
    corpus = build_corpus([tmp_path / "a.txt", tmp_path / "b.md"])
    assert "alpha content" in corpus
    assert "beta content" in corpus
    assert "SOURCE: a.txt" in corpus


def test_expands_folder_sorted(tmp_path: Path):
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "ignore.bin").write_text("nope", encoding="utf-8")
    files = expand_inputs([tmp_path])
    names = [f.name for f in files]
    assert names == ["a.txt", "z.txt"]  # sorted, .bin excluded


def test_missing_input_raises(tmp_path: Path):
    with pytest.raises(IngestError):
        expand_inputs([tmp_path / "does_not_exist.txt"])


def test_unsupported_type_raises(tmp_path: Path):
    bad = tmp_path / "data.bin"
    bad.write_text("x", encoding="utf-8")
    from slide_gen.ingest import read_one

    with pytest.raises(IngestError):
        read_one(bad)


def test_empty_inputs_raise(tmp_path: Path):
    (tmp_path / "empty.txt").write_text("   ", encoding="utf-8")
    with pytest.raises(IngestError):
        build_corpus([tmp_path / "empty.txt"])
