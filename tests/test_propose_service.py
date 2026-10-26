"""Tests for the propose service layer."""

from pathlib import Path

import pytest

from organizer.ai.base import ClassifierUnavailable
from organizer.ai.capabilities import Capabilities
from organizer.config.schema import (
    ConditionConfig,
    DefaultsConfig,
    RuleConfig,
    RulesConfig,
)
from organizer.propose_service import VALID_MODELS, run_propose
from organizer.storage.repository import Repository


def _rules_cfg(organize_root: Path) -> RulesConfig:
    return RulesConfig(
        version=1,
        organize_root=str(organize_root),
        rules={
            "academics": RuleConfig(
                name="academics",
                priority=10,
                destination="Academics",
                match_any=[
                    ConditionConfig(type="extension", values=["pdf"], confidence=0.8),
                ],
            ),
            "images": RuleConfig(
                name="images",
                priority=20,
                destination="Images",
                match_any=[
                    ConditionConfig(type="extension", values=["jpg"], confidence=0.9),
                ],
            ),
        },
        defaults=DefaultsConfig(
            unmatched_category="uncategorized",
            unmatched_destination="_Uncategorized",
            min_confidence_for_proposal=0.5,
        ),
    )


@pytest.fixture
def seeded_repo(tmp_path: Path) -> Repository:
    """Repo with two scanned files ready for propose."""
    from organizer.rules.models import FileRecord

    repo = Repository(tmp_path / "test.db")
    scan_dir = tmp_path / "incoming"
    scan_dir.mkdir()
    for name, ext in [("lecture_notes.pdf", "pdf"), ("vacation.jpg", "jpg")]:
        f = scan_dir / name
        f.write_text(f"content of {name}", encoding="utf-8")
        repo.upsert_file(
            FileRecord(
                path=str(f),
                filename=name,
                extension=ext,
                size_bytes=len(f.read_bytes()),
                created_at=0.0,
                modified_at=0.0,
            )
        )
    repo.record_scan_root(str(scan_dir))
    return repo


def test_invalid_model_raises(seeded_repo, tmp_path):
    cfg = _rules_cfg(tmp_path / "Organized")
    with pytest.raises(ValueError, match="invalid model"):
        run_propose(seeded_repo, cfg, model="quantum")


def test_rules_model_produces_proposals(seeded_repo, tmp_path):
    cfg = _rules_cfg(tmp_path / "Organized")
    caps = Capabilities(rules=True, ml=False, llm=False, api=False)
    result = run_propose(seeded_repo, cfg, model="rules", caps=caps)

    assert result.backend == "rules"
    assert result.proposals_saved == 2
    assert not result.fell_back
    assert result.category_counts["academics"] == 1
    assert result.category_counts["images"] == 1


def test_unavailable_model_falls_back_to_rules(seeded_repo, tmp_path):
    cfg = _rules_cfg(tmp_path / "Organized")
    caps = Capabilities(
        rules=True, ml=False, llm=False, api=False,
        reasons={"llm": "not implemented"},
    )
    result = run_propose(seeded_repo, cfg, model="llm", caps=caps)

    assert result.backend == "rules"
    assert result.fell_back is True
    assert result.fallback_reason == "not implemented"
    assert result.proposals_saved == 2


def test_unavailable_model_no_fallback_raises(seeded_repo, tmp_path):
    cfg = _rules_cfg(tmp_path / "Organized")
    caps = Capabilities(
        rules=True, ml=False, llm=False, api=False,
        reasons={"llm": "not implemented"},
    )
    with pytest.raises(ClassifierUnavailable):
        run_propose(seeded_repo, cfg, model="llm", caps=caps, no_fallback=True)


def test_no_unproposed_files_returns_zero(seeded_repo, tmp_path):
    from organizer.rules.models import Proposal

    cfg = _rules_cfg(tmp_path / "Organized")
    # Pre-add a pending proposal so all files are "already proposed"
    seeded_repo.save_proposal(
        Proposal(
            source_path="/dummy",
            proposed_category="x",
            proposed_destination="/tmp/x",
            confidence=0.5,
            rationale="dummy",
            file_id=1,
        )
    )
    seeded_repo.save_proposal(
        Proposal(
            source_path="/dummy2",
            proposed_category="x",
            proposed_destination="/tmp/x",
            confidence=0.5,
            rationale="dummy",
            file_id=2,
        )
    )

    caps = Capabilities(rules=True, ml=False, llm=False, api=False)
    result = run_propose(seeded_repo, cfg, model="rules", caps=caps)
    assert result.proposals_saved == 0


def test_valid_models_constant():
    assert "rules" in VALID_MODELS
    assert "ml" in VALID_MODELS
    assert "llm" in VALID_MODELS
    assert "api" in VALID_MODELS