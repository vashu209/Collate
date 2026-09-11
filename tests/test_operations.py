"""Tests for move and rollback round-trip operations using tmp_path."""

from pathlib import Path
import pytest

from organizer.dedup.hasher import compute_file_hash
from organizer.operations.mover import FileMover
from organizer.operations.rollback import RollbackManager
from organizer.rules.models import FileRecord, Proposal
from organizer.storage.repository import Repository
from organizer.utils.paths import resolve_collision_free_path


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    """Fixture providing a temporary repository with clean SQLite DB."""
    db_file = tmp_path / "test_organizer.db"
    return Repository(db_file)


def test_collision_free_path(tmp_path: Path):
    """Verify collision-safe naming appends numeric suffixes."""
    file1 = tmp_path / "document.pdf"
    file1.write_text("existing", encoding="utf-8")

    path1 = resolve_collision_free_path(file1)
    assert path1.name == "document_1.pdf"

    # Create document_1.pdf and check next suffix
    path1.write_text("existing 1", encoding="utf-8")
    path2 = resolve_collision_free_path(file1)
    assert path2.name == "document_2.pdf"


def test_move_and_rollback_round_trip(tmp_path: Path, repo: Repository):
    """Create files, move them, roll back, and assert the filesystem matches the original state exactly."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    source_file = source_dir / "report.docx"
    content = b"Original binary report content \x00\x01\x02"
    source_file.write_bytes(content)
    original_hash = compute_file_hash(source_file)

    # Scanned file record
    record = FileRecord(
        path=str(source_file),
        filename=source_file.name,
        extension="docx",
        size_bytes=len(content),
        created_at=0.0,
        modified_at=0.0,
        sha256=original_hash,
    )
    file_id = repo.upsert_file(record)

    # Proposal
    target_path = dest_dir / "report.docx"
    proposal = Proposal(
        file_id=file_id,
        source_path=str(source_file),
        proposed_category="documents",
        proposed_destination=str(target_path),
        confidence=0.8,
        rationale="Test proposal",
    )
    prop_id = repo.save_proposal(proposal)

    mover = FileMover(repo)
    success, operation, err = mover.execute_move(proposal)

    assert success is True
    assert operation is not None
    assert err is None

    # Verify source is gone and destination has file with identical hash
    assert not source_file.exists()
    assert target_path.exists()
    assert compute_file_hash(target_path) == original_hash

    # Verify operation log in database
    op_record = repo.get_operation_by_id(operation.id)
    assert op_record is not None
    assert op_record.status == "completed"

    # Now execute rollback
    rollback_mgr = RollbackManager(repo)
    rollback_result = rollback_mgr.rollback_operation(operation)

    assert rollback_result.success is True
    # Assert filesystem matches the original state exactly
    assert source_file.exists()
    assert not target_path.exists()
    assert compute_file_hash(source_file) == original_hash
    assert source_file.read_bytes() == content

    # Verify operation status updated to rolled_back
    updated_op = repo.get_operation_by_id(operation.id)
    assert updated_op.status == "rolled_back"
    assert updated_op.rolled_back_at is not None


def test_rollback_refuses_modified_file(tmp_path: Path, repo: Repository):
    """Verify rollback refuses to restore if the file at destination was altered."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    source_file = source_dir / "data.csv"
    source_file.write_text("original csv", encoding="utf-8")
    original_hash = compute_file_hash(source_file)

    proposal = Proposal(
        source_path=str(source_file),
        proposed_category="documents",
        proposed_destination=str(dest_dir / "data.csv"),
        confidence=0.9,
        rationale="Test",
    )

    mover = FileMover(repo)
    success, operation, _ = mover.execute_move(proposal)
    assert success is True

    # Tamper with destination file
    dest_file = Path(operation.destination_path)
    dest_file.write_text("tampered content", encoding="utf-8")

    # Attempt rollback
    rollback_mgr = RollbackManager(repo)
    result = rollback_mgr.rollback_operation(operation)

    assert result.success is False
    assert "Integrity check failed" in result.message
    # Source file should NOT have been overwritten with tampered content
    assert not source_file.exists()
    assert dest_file.exists()
