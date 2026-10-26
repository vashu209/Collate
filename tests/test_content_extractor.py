"""Tests for the content extractor."""

from pathlib import Path

from organizer.ai.content_extractor import SimpleContentExtractor


def test_text_file_includes_body(tmp_path: Path):
    f = tmp_path / "notes.txt"
    f.write_text("CS229 lecture on linear regression", encoding="utf-8")

    snippet = SimpleContentExtractor().extract_content(f)

    assert "notes.txt" in snippet
    assert "CS229 lecture" in snippet
    assert tmp_path.name in snippet


def test_binary_file_filename_only(tmp_path: Path):
    f = tmp_path / "photo.bin"
    f.write_bytes(b"\x00\x01\x02\x03" * 100)

    snippet = SimpleContentExtractor().extract_content(f)

    assert "photo.bin" in snippet
    assert tmp_path.name in snippet


def test_snippet_is_truncated(tmp_path: Path):
    f = tmp_path / "huge.txt"
    f.write_text("word " * 5000, encoding="utf-8")

    snippet = SimpleContentExtractor(max_chars=100).extract_content(f)

    assert len(snippet) <= 100


def test_unreadable_file_does_not_raise(tmp_path: Path):
    f = tmp_path / "locked.txt"
    f.write_text("data", encoding="utf-8")
    f.chmod(0o000)

    try:
        snippet = SimpleContentExtractor().extract_content(f)
    finally:
        f.chmod(0o644)

    assert "locked.txt" in snippet


def test_missing_file_returns_metadata_only(tmp_path: Path):
    f = tmp_path / "does-not-exist.txt"
    snippet = SimpleContentExtractor().extract_content(f)
    assert "does-not-exist.txt" in snippet