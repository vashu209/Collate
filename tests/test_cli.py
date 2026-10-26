"""End-to-end tests for organizer CLI commands using Typer CliRunner."""

from pathlib import Path
import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path):
    """Setup temporary workspace with files, config, and db path for CLI testing."""
    scan_dir = tmp_path / "incoming"
    scan_dir.mkdir()

    # Create test files
    (scan_dir / "lecture_1.pdf").write_text("lecture notes", encoding="utf-8")
    (scan_dir / "photo.jpg").write_text("photo data", encoding="utf-8")
    (scan_dir / "photo_dup.jpg").write_text("photo data", encoding="utf-8")
    (scan_dir / "notes.txt").write_text("some random thoughts", encoding="utf-8")

    db_path = tmp_path / "test.db"
    rules_file = tmp_path / "rules.yaml"
    rules_content = f"""
version: 1
organize_root: "{tmp_path.as_posix()}/Organized"

rules:
  academics:
    priority: 10
    destination: Academics
    match_any:
      - type: extension
        values: [pdf]
        confidence: 0.7
      - type: keyword_in_name
        values: [lecture]
        confidence: 0.85

  images:
    priority: 20
    destination: Images
    match_any:
      - type: extension
        values: [jpg]
        confidence: 0.95

defaults:
  unmatched_category: uncategorized
  unmatched_destination: _Uncategorized
  min_confidence_for_proposal: 0.5
"""
    rules_file.write_text(rules_content.strip(), encoding="utf-8")

    return {
        "scan_dir": scan_dir,
        "db_path": db_path,
        "rules_file": rules_file,
        "organize_root": tmp_path / "Organized",
    }


def test_cli_full_workflow(cli_env):
    """Test full CLI lifecycle: scan -> duplicates -> propose -> approve (dry-run) -> approve (--all) -> status -> rollback."""
    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    # 1. Scan
    scan_res = runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    assert scan_res.exit_code == 0
    assert "Scan complete" in scan_res.output

    # 2. Duplicates
    dup_res = runner.invoke(app, ["duplicates", "--db", db_path])
    assert dup_res.exit_code == 0
    normalized_output = dup_res.output.replace("\n", "").replace(" ", "").replace("│", "")
    assert "photo.jpg" in normalized_output
    assert "photo_dup.jpg" in normalized_output

    # 3. Propose
    prop_res = runner.invoke(app, ["propose", "--model", "rules", "--config", rules_file, "--db", db_path])
    assert prop_res.exit_code == 0
    assert "Generated Proposals" in prop_res.output

    # 4. Approve --dry-run
    dry_res = runner.invoke(app, ["approve", "--dry-run", "--db", db_path])
    assert dry_res.exit_code == 0
    assert "DRY-RUN PREVIEW" in dry_res.output

    # Files should not have moved yet
    assert (cli_env["scan_dir"] / "lecture_1.pdf").exists()

    # 5. Approve --all
    app_res = runner.invoke(app, ["approve", "--all", "--db", db_path])
    assert app_res.exit_code == 0
    assert "Batch execution finished" in app_res.output

    # Verify files moved into Category folders inside the scan_dir
    assert not (cli_env["scan_dir"] / "lecture_1.pdf").exists()
    assert (cli_env["scan_dir"] / "Academics" / "lecture_1.pdf").exists()
    assert (cli_env["scan_dir"] / "Images" / "photo.jpg").exists()

    # 6. Status
    status_res = runner.invoke(app, ["status", "--db", db_path])
    assert status_res.exit_code == 0
    assert "Autonomous File Organizer" in status_res.output

    # 7. Rollback --all
    roll_res = runner.invoke(app, ["rollback", "--all", "--db", db_path])
    assert roll_res.exit_code == 0
    assert "RESTORED" in roll_res.output

    # Verify files restored to original locations
    assert (cli_env["scan_dir"] / "lecture_1.pdf").exists()
    assert (cli_env["scan_dir"] / "photo.jpg").exists()
    assert not (cli_env["scan_dir"] / "Academics" / "lecture_1.pdf").exists()


def test_cli_approve_category(cli_env):
    """Test bulk approval by category (--approve-category)."""
    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    runner.invoke(app, ["propose", "--model", "rules", "--config", rules_file, "--db", db_path])

    # Approve only 'academics' category
    res = runner.invoke(app, ["approve", "--approve-category", "academics", "--db", db_path])
    assert res.exit_code == 0
    assert "Category approval completed: 1 succeeded" in res.output

    # Academics file moved, image file not moved
    assert (cli_env["scan_dir"] / "Academics" / "lecture_1.pdf").exists()
    assert (cli_env["scan_dir"] / "photo.jpg").exists()


def test_cli_approve_range(cli_env):
    """Test bulk approval by display range (--approve-range)."""
    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    runner.invoke(app, ["propose", "--config", rules_file, "--db", db_path])

    # Approve range 1-2 using 'review' command
    res = runner.invoke(app, ["review", "--approve-range", "1-2", "--db", db_path])
    assert res.exit_code == 0
    assert "Range approval completed: 2 succeeded" in res.output


def test_cli_filter_category_and_pagination(cli_env):
    """Test paginated and category-filtered preview in review."""
    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    runner.invoke(app, ["propose", "--model", "rules", "--config", rules_file, "--db", db_path])

    # Preview with filter-category Academics and page-size 1
    res = runner.invoke(
        app,
        ["review", "--dry-run", "--filter-category", "academics", "--page-size", "1", "--db", db_path],
    )
    assert res.exit_code == 0
    assert "Page 1 of 1" in res.output
    assert "academics" in res.output.lower()


def test_cli_interactive_skip(cli_env):
    """Test interactive skip command leaves proposals pending in database."""
    from organizer.storage.repository import Repository

    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    runner.invoke(app, ["propose", "--config", rules_file, "--db", db_path])

    repo = Repository(db_path)
    initial_pending = repo.get_pending_proposals()
    assert len(initial_pending) > 0

    # Simulate typing 'sa' (skip all) then 'q' (quit)
    res = runner.invoke(app, ["review", "--db", db_path], input="sa\nq\n")
    assert res.exit_code == 0

    # Ensure files did NOT move
    assert (cli_env["scan_dir"] / "lecture_1.pdf").exists()

    # Crucial requirement: skipped files remain in pending status in the database
    after_pending = repo.get_pending_proposals()
    assert len(after_pending) == len(initial_pending)


def test_cli_date_stamped_destination(tmp_path):
    """Test date-stamped folder organization when category folder already exists."""
    from datetime import datetime

    scan_dir = tmp_path / "target_scan"
    scan_dir.mkdir()
    (scan_dir / "assignment.pdf").write_text("assignment content", encoding="utf-8")

    # Pre-create category folder Academics
    (scan_dir / "Academics").mkdir()

    db_path = tmp_path / "date_test.db"
    rules_file = tmp_path / "rules.yaml"
    rules_content = f"""
version: 1
organize_root: "{scan_dir.as_posix()}"
rules:
  academics:
    priority: 10
    destination: Academics
    match_any:
      - type: extension
        values: [pdf]
        confidence: 0.8
defaults:
  unmatched_category: uncategorized
  unmatched_destination: _Uncategorized
  min_confidence_for_proposal: 0.5
"""
    rules_file.write_text(rules_content.strip(), encoding="utf-8")

    # Scan and propose
    runner.invoke(app, ["scan", str(scan_dir), "--db", str(db_path)])
    runner.invoke(app, ["propose", "--model", "rules", "--config", str(rules_file), "--db", str(db_path)])

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Dry-run review should display the preview
    dry_res = runner.invoke(app, ["review", "--dry-run", "--db", str(db_path)])
    assert dry_res.exit_code == 0
    assert "DRY-RUN PREVIEW" in dry_res.output

    # Verify stored proposal destination has today_str
    from organizer.storage.repository import Repository
    repo = Repository(str(db_path))
    proposals = repo.get_pending_proposals()
    assert len(proposals) == 1
    assert today_str in proposals[0].proposed_destination

    # Approve and verify move into date-stamped folder
    app_res = runner.invoke(app, ["approve", "--all", "--db", str(db_path)])
    assert app_res.exit_code == 0

    expected_file = scan_dir / "Academics" / today_str / "assignment.pdf"
    assert expected_file.exists()


def test_repository_live_pending_update(tmp_path):
    """Verify that updating a proposal status in SQLite immediately reflects in get_pending_proposals()."""
    from organizer.storage.repository import Repository
    from organizer.rules.models import FileRecord, Proposal

    db_path = tmp_path / "repo_test.db"
    repo = Repository(db_path)

    # 1. Insert file and proposal
    file_rec = FileRecord(
        path=str(tmp_path / "doc.txt"),
        filename="doc.txt",
        extension="txt",
        size_bytes=50,
        created_at=0.0,
        modified_at=0.0,
    )
    fid = repo.upsert_file(file_rec)
    proposal = Proposal(
        file_id=fid,
        source_path=file_rec.path,
        proposed_category="documents",
        proposed_destination=str(tmp_path / "Documents" / "doc.txt"),
        confidence=0.8,
        rationale="test",
        status="pending",
    )
    pid = repo.save_proposal(proposal)

    # Initially proposal is in pending list
    pending_list = repo.get_pending_proposals()
    assert len(pending_list) == 1
    assert pending_list[0].id == pid

    # 2. Update status to 'executed'
    repo.update_proposal_status(pid, "executed")

    # Re-fetch: must immediately reflect change with zero stale cache
    updated_pending = repo.get_pending_proposals()
    assert len(updated_pending) == 0


def test_cli_live_refresh_and_approved_disappears(cli_env):
    """Test interactive approve immediately removes file from pending DB list."""
    from organizer.storage.repository import Repository

    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    runner.invoke(app, ["propose", "--config", rules_file, "--db", db_path])

    repo = Repository(db_path)
    initial_pending = repo.get_pending_proposals()
    initial_count = len(initial_pending)
    assert initial_count >= 2

    # In interactive review, approve item 1 ('y 1') then quit ('q')
    res = runner.invoke(app, ["review", "--db", db_path], input="y 1\nq\n")
    assert res.exit_code == 0

    # Fresh DB check: pending count must decrease by 1
    fresh_pending = repo.get_pending_proposals()
    assert len(fresh_pending) == initial_count - 1
    # The approved file's proposal is no longer in pending list
    assert initial_pending[0].id not in [p.id for p in fresh_pending]


def test_cli_navigation_back_page(cli_env):
    """Test backwards navigation ('b') in paginated view (e.g. Page 2 back to Page 1)."""
    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    runner.invoke(app, ["propose", "--config", rules_file, "--db", db_path])

    # Navigate forward ('n' to Page 2), then back ('b' to Page 1), then quit ('q')
    res = runner.invoke(app, ["review", "--page-size", "1", "--db", db_path], input="n\nb\nq\n")
    assert res.exit_code == 0
    assert "Page 2 of" in res.output
    assert "Navigating back to Page 1" in res.output


def test_cli_navigation_back_item_view(cli_env):
    """Test inspecting a specific file ('v 1') and returning via 'b' without changing status."""
    from organizer.storage.repository import Repository

    scan_dir = str(cli_env["scan_dir"])
    db_path = str(cli_env["db_path"])
    rules_file = str(cli_env["rules_file"])

    runner.invoke(app, ["scan", scan_dir, "--db", db_path])
    runner.invoke(app, ["propose", "--config", rules_file, "--db", db_path])

    repo = Repository(db_path)
    before_pending = repo.get_pending_proposals()

    # Enter view mode for item 1 ('v 1'), choose back ('b'), then quit ('q')
    res = runner.invoke(app, ["review", "--db", db_path], input="v 1\nb\nq\n")
    assert res.exit_code == 0
    assert "Proposal Inspection: #1" in res.output
    assert "Returning to proposal list view" in res.output

    # File status remains unchanged (pending)
    after_pending = repo.get_pending_proposals()
    assert len(after_pending) == len(before_pending)
