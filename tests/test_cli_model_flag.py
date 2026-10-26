"""Tests for the --model flag on organizer propose."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path):
    scan_dir = tmp_path / "incoming"
    scan_dir.mkdir()
    (scan_dir / "lecture_notes.pdf").write_text("academic content", encoding="utf-8")
    (scan_dir / "vacation_photo.jpg").write_text("image data", encoding="utf-8")

    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        f"""
version: 1
organize_root: "{tmp_path.as_posix()}/Organized"
rules:
  academics:
    priority: 10
    destination: Academics
    match_any:
      - type: extension
        values: [pdf]
        confidence: 0.8
  images:
    priority: 20
    destination: Images
    match_any:
      - type: extension
        values: [jpg]
        confidence: 0.9
defaults:
  unmatched_category: uncategorized
  unmatched_destination: _Uncategorized
  min_confidence_for_proposal: 0.5
""".strip(),
        encoding="utf-8",
    )

    return {
        "scan_dir": scan_dir,
        "db_path": tmp_path / "test.db",
        "rules_file": rules_file,
    }


def test_propose_model_rules(cli_env):
    runner.invoke(app, ["scan", str(cli_env["scan_dir"]), "--db", str(cli_env["db_path"])])
    res = runner.invoke(
        app,
        [
            "propose",
            "--model", "rules",
            "--config", str(cli_env["rules_file"]),
            "--db", str(cli_env["db_path"]),
        ],
    )
    assert res.exit_code == 0
    assert "backend=rules" in res.output or "backend [bold]rules" in res.output


def test_propose_invalid_model(cli_env):
    res = runner.invoke(
        app,
        ["propose", "--model", "quantum", "--db", str(cli_env["db_path"])],
    )
    assert res.exit_code == 1
    assert "invalid --model" in res.output


def test_propose_unavailable_no_fallback(cli_env):
    runner.invoke(app, ["scan", str(cli_env["scan_dir"]), "--db", str(cli_env["db_path"])])
    res = runner.invoke(
        app,
        [
            "propose",
            "--model", "llm",
            "--no-fallback",
            "--config", str(cli_env["rules_file"]),
            "--db", str(cli_env["db_path"]),
        ],
    )
    assert res.exit_code == 1
    assert "unavailable" in res.output.lower()


def test_propose_unavailable_falls_back(cli_env):
    runner.invoke(app, ["scan", str(cli_env["scan_dir"]), "--db", str(cli_env["db_path"])])
    res = runner.invoke(
        app,
        [
            "propose",
            "--model", "llm",
            "--config", str(cli_env["rules_file"]),
            "--db", str(cli_env["db_path"]),
        ],
    )
    assert res.exit_code == 0
    assert "fell back to" in res.output or "falling back" in res.output


@pytest.mark.skipif(
    not (
        Path(__file__).parent.parent
        / "organizer" / "ai" / "models" / "minilm-l6-v2" / "model.onnx"
    ).exists(),
    reason="MiniLM model not fetched",
)
def test_propose_ml_bootstraps_and_classifies(cli_env):
    from organizer.storage.repository import Repository

    runner.invoke(app, ["scan", str(cli_env["scan_dir"]), "--db", str(cli_env["db_path"])])
    res = runner.invoke(
        app,
        [
            "propose",
            "--model", "ml",
            "--config", str(cli_env["rules_file"]),
            "--db", str(cli_env["db_path"]),
        ],
    )
    assert res.exit_code == 0
    assert "bootstrapped" in res.output.lower()
    assert "backend=ml" in res.output or "backend [bold]ml" in res.output

    repo = Repository(cli_env["db_path"])
    pending = repo.get_pending_proposals()
    assert len(pending) > 0