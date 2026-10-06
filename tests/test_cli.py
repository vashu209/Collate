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
    prop_res = runner.invoke(app, ["propose", "--config", rules_file, "--db", db_path])
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

    # Verify files moved to Organized directory
    assert not (cli_env["scan_dir"] / "lecture_1.pdf").exists()
    assert (cli_env["organize_root"] / "Academics" / "lecture_1.pdf").exists()
    assert (cli_env["organize_root"] / "Images" / "photo.jpg").exists()

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
    assert not (cli_env["organize_root"] / "Academics" / "lecture_1.pdf").exists()
