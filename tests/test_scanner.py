"""Tests for filesystem scanner and metadata extraction."""

from pathlib import Path
import pytest

from organizer.dedup.hasher import compute_file_hash, find_duplicates
from organizer.rules.models import FileRecord
from organizer.scanning.metadata import extract_metadata
from organizer.scanning.scanner import scan_directory


def test_metadata_extraction(tmp_path: Path):
    """Test metadata extraction on a created file."""
    test_file = tmp_path / "sample.txt"
    test_content = b"Hello, world!"
    test_file.write_bytes(test_content)

    size, ctime, mtime, ext, mime, is_link = extract_metadata(test_file)

    assert size == len(test_content)
    assert ext == "txt"
    assert is_link is False
    assert ctime > 0
    assert mtime > 0


def test_scanner_traversal_recursive(tmp_path: Path):
    """Test recursive directory scanning yielding FileRecords."""
    sub_dir = tmp_path / "subfolder"
    sub_dir.mkdir()

    file1 = tmp_path / "file1.txt"
    file1.write_text("file 1 content", encoding="utf-8")

    file2 = sub_dir / "file2.pdf"
    file2.write_bytes(b"%PDF-1.4 header content")

    records = list(scan_directory(tmp_path, recursive=True))
    assert len(records) == 2

    filenames = {r.filename for r in records}
    assert "file1.txt" in filenames
    assert "file2.pdf" in filenames

    # Verify SHA-256 is present
    for r in records:
        assert r.sha256 is not None
        assert len(r.sha256) == 64


def test_scanner_non_recursive(tmp_path: Path):
    """Test non-recursive directory scanning does not enter subdirectories."""
    sub_dir = tmp_path / "subfolder"
    sub_dir.mkdir()

    file1 = tmp_path / "file1.txt"
    file1.write_text("top level", encoding="utf-8")

    file2 = sub_dir / "file2.txt"
    file2.write_text("nested", encoding="utf-8")

    records = list(scan_directory(tmp_path, recursive=False))
    assert len(records) == 1
    assert records[0].filename == "file1.txt"


def test_find_duplicates(tmp_path: Path):
    """Test duplicate detection via SHA-256 hash."""
    file1 = tmp_path / "orig.txt"
    file1.write_text("identical content", encoding="utf-8")

    file2 = tmp_path / "copy.txt"
    file2.write_text("identical content", encoding="utf-8")

    file3 = tmp_path / "different.txt"
    file3.write_text("different content", encoding="utf-8")

    records = list(scan_directory(tmp_path, recursive=False))
    duplicates = find_duplicates(records)

    assert len(duplicates) == 1
    dup_group = next(iter(duplicates.values()))
    assert len(dup_group) == 2
    dup_names = {r.filename for r in dup_group}
    assert dup_names == {"orig.txt", "copy.txt"}
