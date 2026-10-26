"""Tests for the TrainingStore."""

from pathlib import Path

import pytest

from organizer.ai.base import Embedder
from organizer.ai.training_store import TrainingStore
from organizer.rules.models import FeedbackRecord
from organizer.storage.repository import Repository


class FakeEmbedder(Embedder):
    """Deterministic embedder for tests: hashes text into a small vector."""

    def generate_embedding(self, text: str):
        h = sum(ord(c) for c in text) % 97
        return [float(h)] * 4


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "test.db")


def _seed_feedback(repo: Repository, records):
    for r in records:
        repo.save_feedback(r)


def test_load_skips_missing_files(repo):
    store = TrainingStore(repository=repo, embedder=FakeEmbedder())
    _seed_feedback(
        repo,
        [
            FeedbackRecord(
                source_path="/does/not/exist.pdf",
                proposed_category="academics",
                proposed_destination="/tmp/academics/x.pdf",
                action="approved",
            ),
        ],
    )
    assert store.load() == 0
    assert store.is_empty()


def test_load_approved_and_modified(repo, tmp_path: Path):
    f = tmp_path / "lecture.pdf"
    f.write_text("course notes", encoding="utf-8")

    _seed_feedback(
        repo,
        [
            FeedbackRecord(
                source_path=str(f),
                proposed_category="academics",
                proposed_destination="/tmp/Academics/lecture.pdf",
                action="approved",
            ),
        ],
    )

    store = TrainingStore(repository=repo, embedder=FakeEmbedder())
    assert store.load() == 1
    assert store.examples[0].category == "academics"
    assert store.examples[0].source == "feedback"
    assert store.examples[0].vector is not None


def test_load_rejected_tracked_not_stored(repo, tmp_path: Path):
    f = tmp_path / "img.png"
    f.write_text("data", encoding="utf-8")

    _seed_feedback(
        repo,
        [
            FeedbackRecord(
                source_path=str(f),
                proposed_category="images",
                proposed_destination="/tmp/Images/img.png",
                action="rejected",
            ),
        ],
    )

    store = TrainingStore(repository=repo, embedder=FakeEmbedder())
    assert store.load() == 0
    assert "images" in store.rejected_categories


def test_add_pseudolabels(repo):
    store = TrainingStore(repository=repo, embedder=FakeEmbedder())
    n = store.add_pseudolabels(
        [
            ("lecture notes", "academics", "/tmp/Academics"),
            ("vacation photo", "images", "/tmp/Images"),
        ]
    )
    assert n == 2
    assert not store.is_empty()
    assert {ex.source for ex in store.examples} == {"pseudolabel"}