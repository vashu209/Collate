"""Classifier implementations (Stage 4 replaces the embedding stub)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from organizer.ai.base import Classifier, Embedder
from organizer.config.schema import RulesConfig
from organizer.rules.models import FileRecord, Proposal


class AIClassifier(Classifier):
    """Placeholder for a generic AI classifier. Raises until implemented."""

    def classify(self, record: FileRecord) -> Proposal:
        raise NotImplementedError("AIClassifier is not implemented yet.")


class EmbeddingClassifier(Classifier):
    """Placeholder embedding-based classifier. Stage 4 replaces this."""

    def __init__(
        self,
        rules_cfg: RulesConfig,
        embedder: Embedder,
        training_store,
        *,
        organize_root: Optional[Union[str, Path]] = None,
        today_str: Optional[str] = None,
    ) -> None:
        self.rules_cfg = rules_cfg
        self.embedder = embedder
        self.training_store = training_store
        self.organize_root = organize_root
        self.today_str = today_str

    def classify(self, record: FileRecord) -> Proposal:
        raise NotImplementedError(
            "EmbeddingClassifier is not implemented yet (Stage 4)."
        )