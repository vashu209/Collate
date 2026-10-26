"""Tests for the classifier registry."""

import pytest

from organizer.ai import registry
from organizer.ai.base import ClassifierUnavailable
from organizer.ai.capabilities import Capabilities
from organizer.config.schema import (
    ConditionConfig,
    DefaultsConfig,
    RuleConfig,
    RulesConfig,
)
from organizer.rules.engine import RuleBasedClassifier


@pytest.fixture
def rules_cfg() -> RulesConfig:
    return RulesConfig(
        version=1,
        organize_root="/tmp/Organized",
        rules={
            "documents": RuleConfig(
                name="documents",
                priority=5,
                destination="Documents",
                match_any=[
                    ConditionConfig(type="extension", values=["txt"], confidence=0.5),
                ],
            ),
        },
        defaults=DefaultsConfig(
            unmatched_category="uncategorized",
            unmatched_destination="_Uncategorized",
            min_confidence_for_proposal=0.5,
        ),
    )


def test_available_models_lists_rules_and_ml():
    names = registry.available_models()
    assert "rules" in names
    assert "ml" in names


def test_build_rules_returns_rule_based(rules_cfg):
    caps = Capabilities(rules=True, ml=False, llm=False, api=False)
    clf = registry.build_classifier("rules", rules_cfg, caps=caps)
    assert isinstance(clf, RuleBasedClassifier)


def test_build_rules_forwards_organize_root(rules_cfg, tmp_path):
    caps = Capabilities(rules=True, ml=False, llm=False, api=False)
    clf = registry.build_classifier(
        "rules", rules_cfg, caps=caps, organize_root=tmp_path
    )
    assert isinstance(clf, RuleBasedClassifier)
    assert clf.organize_root == tmp_path.resolve()


def test_build_ml_raises_when_unavailable(rules_cfg):
    caps = Capabilities(
        rules=True,
        ml=False,
        llm=False,
        api=False,
        reasons={"ml": "missing onnxruntime"},
    )
    with pytest.raises(ClassifierUnavailable) as exc:
        registry.build_classifier("ml", rules_cfg, caps=caps)
    assert "missing onnxruntime" in str(exc.value)


def test_unknown_model_raises(rules_cfg):
    caps = Capabilities(rules=True, ml=False, llm=False, api=False)
    with pytest.raises(ClassifierUnavailable) as exc:
        registry.build_classifier("quantum", rules_cfg, caps=caps)
    assert "unknown classifier" in str(exc.value)
    assert exc.value.hint is not None


def test_unimplemented_tier_raises_unknown(rules_cfg):
    # "llm" has no factory yet, so it should be reported as unknown,
    # not as "unavailable".
    caps = Capabilities(rules=True, ml=False, llm=True, api=False)
    with pytest.raises(ClassifierUnavailable) as exc:
        registry.build_classifier("llm", rules_cfg, caps=caps)
    assert "unknown classifier" in str(exc.value)