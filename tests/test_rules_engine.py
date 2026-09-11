"""Tests for the rule-based classification engine, schema, and priority resolution."""

import pytest

from organizer.ai.base import Classifier
from organizer.ai.classifier import AIClassifier
from organizer.config.schema import (
    ConditionConfig,
    ConfigValidationError,
    DefaultsConfig,
    RuleConfig,
    RulesConfig,
)
from organizer.rules.engine import RuleBasedClassifier, RuleEngine
from organizer.rules.models import FileRecord


@pytest.fixture
def sample_config() -> RulesConfig:
    """Fixture providing a standard RulesConfig."""
    return RulesConfig(
        version=1,
        organize_root="/test/Organized",
        rules={
            "academics": RuleConfig(
                name="academics",
                priority=10,
                destination="Academics",
                match_any=[
                    ConditionConfig(type="extension", values=["pdf", "docx"], confidence=0.7),
                    ConditionConfig(type="keyword_in_name", values=["lecture", "homework"], confidence=0.85),
                    ConditionConfig(type="path_contains", values=["Semester"], confidence=0.75),
                ],
            ),
            "images": RuleConfig(
                name="images",
                priority=20,
                destination="Images",
                match_any=[
                    ConditionConfig(type="extension", values=["jpg", "png"], confidence=0.95),
                ],
            ),
            "documents": RuleConfig(
                name="documents",
                priority=5,
                destination="Documents",
                match_any=[
                    ConditionConfig(type="extension", values=["pdf", "txt"], confidence=0.5),
                ],
            ),
        },
        defaults=DefaultsConfig(
            unmatched_category="uncategorized",
            unmatched_destination="_Uncategorized",
            min_confidence_for_proposal=0.5,
        ),
    )


def test_classifier_implements_ai_interface(sample_config):
    """Verify that RuleBasedClassifier implements the Classifier protocol/ABC."""
    engine = RuleBasedClassifier(sample_config)
    assert isinstance(engine, Classifier)
    assert isinstance(engine, RuleEngine)


def test_ai_placeholder_raises():
    """Verify that the Phase 2 AIClassifier placeholder raises NotImplementedError."""
    ai = AIClassifier()
    record = FileRecord(
        path="/tmp/test.txt",
        filename="test.txt",
        extension="txt",
        size_bytes=100,
        created_at=0.0,
        modified_at=0.0,
    )
    with pytest.raises(NotImplementedError):
        ai.classify(record)


def test_extension_matching(sample_config):
    """Test matching by extension (case-insensitive)."""
    engine = RuleBasedClassifier(sample_config)
    record = FileRecord(
        path="/tmp/photo.PNG",
        filename="photo.PNG",
        extension="png",
        size_bytes=1024,
        created_at=0.0,
        modified_at=0.0,
    )
    proposal = engine.classify(record)
    assert proposal.proposed_category == "images"
    assert "Images" in proposal.proposed_destination
    assert proposal.confidence == 0.95


def test_keyword_in_name_matching(sample_config):
    """Test matching by keyword in filename (case-insensitive)."""
    engine = RuleBasedClassifier(sample_config)
    record = FileRecord(
        path="/tmp/BIO_Lecture_Week1.txt",
        filename="BIO_Lecture_Week1.txt",
        extension="txt",
        size_bytes=1024,
        created_at=0.0,
        modified_at=0.0,
    )
    proposal = engine.classify(record)
    # academics (priority 10, confidence 0.85 via keyword) vs documents (priority 5, confidence 0.5 via extension txt)
    assert proposal.proposed_category == "academics"
    assert proposal.confidence == 0.85
    assert "lecture" in proposal.rationale.lower()


def test_path_contains_matching(sample_config):
    """Test matching by path_contains."""
    engine = RuleBasedClassifier(sample_config)
    record = FileRecord(
        path="/home/user/Semester_2026/random.dat",
        filename="random.dat",
        extension="dat",
        size_bytes=1024,
        created_at=0.0,
        modified_at=0.0,
    )
    proposal = engine.classify(record)
    assert proposal.proposed_category == "academics"
    assert proposal.confidence == 0.75
    assert "Semester" in proposal.rationale


def test_priority_tie_breaking(sample_config):
    """When multiple rules match, highest priority category wins."""
    engine = RuleBasedClassifier(sample_config)
    # File has .pdf -> matches 'academics' (priority 10) AND 'documents' (priority 5)
    record = FileRecord(
        path="/tmp/regular_book.pdf",
        filename="regular_book.pdf",
        extension="pdf",
        size_bytes=1024,
        created_at=0.0,
        modified_at=0.0,
    )
    proposal = engine.classify(record)
    assert proposal.proposed_category == "academics"
    assert proposal.confidence == 0.7


def test_unmatched_fallback(sample_config):
    """Files matching no rules fall back to defaults with confidence 0.0."""
    engine = RuleBasedClassifier(sample_config)
    record = FileRecord(
        path="/tmp/unknown.xyz",
        filename="unknown.xyz",
        extension="xyz",
        size_bytes=1024,
        created_at=0.0,
        modified_at=0.0,
    )
    proposal = engine.classify(record)
    assert proposal.proposed_category == "uncategorized"
    assert "_Uncategorized" in proposal.proposed_destination
    assert proposal.confidence == 0.0


def test_invalid_condition_type():
    """Verify validation error when condition type is unknown."""
    with pytest.raises(ConfigValidationError):
        ConditionConfig(type="invalid_type", values=["a"], confidence=0.8)


def test_invalid_confidence_range():
    """Verify validation error when confidence is outside [0.0, 1.0]."""
    with pytest.raises(ConfigValidationError):
        ConditionConfig(type="extension", values=["pdf"], confidence=1.5)
