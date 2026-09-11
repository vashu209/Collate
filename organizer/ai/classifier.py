"""Placeholder AI classifier for Phase 2."""

from organizer.ai.base import Classifier
from organizer.rules.models import FileRecord, Proposal


class AIClassifier(Classifier):
    """Placeholder AI/ML classifier using multimodal LLM or embedding-based classification."""

    def classify(self, record: FileRecord) -> Proposal:
        raise NotImplementedError(
            "AIClassifier is a placeholder for Phase 2 (LLM/ML Classification). "
            "Use RuleBasedClassifier in organizer.rules.engine for Phase 1."
        )
