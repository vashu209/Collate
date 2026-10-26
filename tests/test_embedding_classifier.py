"""Tests for the EmbeddingClassifier."""

from pathlib import Path
from typing import Union
import numpy as np

import pytest

from organizer.ai.base import ClassifierUnavailable, ContentExtractor, Embedder
from organizer.ai.classifier import EmbeddingClassifier
from organizer.ai.training_store import TrainingExample, TrainingStore
from organizer.config.schema import DefaultsConfig, RulesConfig
from organizer.rules.models import FileRecord


def _make_cfg() -> RulesConfig:
    return RulesConfig(
        version=1,
        organize_root="/tmp/Organized",
        rules={},
        defaults=DefaultsConfig(
            unmatched_category="uncategorized",
            unmatched_destination="_Uncategorized",
            min_confidence_for_proposal=0.5,
        ),
    )


class FakeEmbedder(Embedder):
    """Maps recognizable keywords to distinguishable vectors."""

    def generate_embedding(self, text: str):
        t = text.lower()
        if "lecture" in t or "academic" in t or "course" in t:
            return [1.0, 0.0, 0.0, 0.0]
        if "photo" in t or "vacation" in t or "image" in t:
            return [0.0, 1.0, 0.0, 0.0]
        if "invoice" in t or "receipt" in t:
            return [0.0, 0.0, 1.0, 0.0]
        return [0.0, 0.0, 0.0, 1.0]


class FakeExtractor(ContentExtractor):
    def __init__(self, text: str = "") -> None:
        self._text = text

    def extract_content(self, file_path: Union[str, Path]) -> str:
        return self._text or Path(file_path).name

def _store_with(examples):
    store = TrainingStore(repository=None, embedder=FakeEmbedder())
    for text, cat, dest, src in examples:
        ex = TrainingExample(text=text, category=cat, destination=dest, source=src)
        ex.vector = np.asarray(FakeEmbedder().generate_embedding(text), dtype=np.float32)
        store.examples.append(ex)
    return store


def _record(path="/tmp/lecture_notes.pdf"):
    return FileRecord(
        path=path,
        filename=Path(path).name,
        extension="pdf",
        size_bytes=100,
        created_at=0.0,
        modified_at=0.0,
    )


def test_classify_picks_majority_neighbor():
    store = _store_with(
        [
            ("academic lecture notes", "academics", "/tmp/Academics", "feedback"),
            ("course homework", "academics", "/tmp/Academics", "feedback"),
            ("another lecture", "academics", "/tmp/Academics", "feedback"),
            ("vacation photo", "images", "/tmp/Images", "feedback"),
        ]
    )
    clf = EmbeddingClassifier(
        _make_cfg(),
        FakeEmbedder(),
        store,
        organize_root="/tmp/Organized",
        extractor=FakeExtractor("lecture notes"),
    )
    proposal = clf.classify(_record())
    assert proposal.proposed_category == "academics"
    assert proposal.confidence >= 0.5
    assert "neighbors" in proposal.rationale


def test_pseudolabels_counted_less():
    """Two pseudo-neighbors lose to one feedback neighbor when pseudo_weight < 0.5."""
    store = _store_with(
        [
            ("academic lecture notes draft", "academics", "/tmp/Academics", "pseudolabel"),
            ("academic lecture notes final", "academics", "/tmp/Academics", "pseudolabel"),
            ("academic lecture summary", "images", "/tmp/Images", "feedback"),
        ]
    )
    clf = EmbeddingClassifier(
        _make_cfg(),
        FakeEmbedder(),
        store,
        organize_root="/tmp/Organized",
        extractor=FakeExtractor("academic lecture notes"),
        pseudo_weight=0.4,
    )
    proposal = clf.classify(_record())
    assert proposal.proposed_category == "images"


def test_low_confidence_falls_back():
    """Zero-similarity query falls back to uncategorized."""
    store = _store_with(
        [
            ("academic lecture notes", "academics", "/tmp/Academics", "feedback"),
        ]
    )
    clf = EmbeddingClassifier(
        _make_cfg(),
        FakeEmbedder(),
        store,
        organize_root="/tmp/Organized",
        extractor=FakeExtractor("random unknown content"),
        ml_min_confidence=0.9,
    )
    proposal = clf.classify(_record("/tmp/unknown.dat"))
    assert proposal.proposed_category == "uncategorized"
    assert proposal.confidence == 0.0
    assert "votes were zero" in proposal.rationale


def test_empty_store_raises():
    store = TrainingStore(repository=None, embedder=FakeEmbedder())
    clf = EmbeddingClassifier(
        _make_cfg(),
        FakeEmbedder(),
        store,
        organize_root="/tmp/Organized",
        extractor=FakeExtractor("x"),
    )
    with pytest.raises(ClassifierUnavailable):
        clf.classify(_record())


def test_rejected_category_penalized():
    """Single-category store: penalty can't flip the vote (documented limitation)."""
    store = _store_with(
        [
            ("invoice document", "documents", "/tmp/Documents", "feedback"),
            ("invoice document", "documents", "/tmp/Documents", "feedback"),
        ]
    )
    store.rejected_categories.add("documents")

    clf = EmbeddingClassifier(
        _make_cfg(),
        FakeEmbedder(),
        store,
        organize_root="/tmp/Organized",
        extractor=FakeExtractor("invoice"),
    )
    proposal = clf.classify(_record("/tmp/invoice.pdf"))
    assert proposal.proposed_category in {"documents", "uncategorized"}