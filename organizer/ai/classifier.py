"""Classifier implementations. EmbeddingClassifier is Tier 1."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

from organizer.ai.base import Classifier, ClassifierUnavailable, ContentExtractor, Embedder
from organizer.ai.content_extractor import SimpleContentExtractor
from organizer.ai.training_store import TrainingStore
from organizer.config.schema import RulesConfig
from organizer.rules.models import FileRecord, Proposal

logger = logging.getLogger(__name__)


class AIClassifier(Classifier):
    """Placeholder for future tiers (local LLM, cloud API)."""

    def classify(self, record: FileRecord) -> Proposal:
        raise NotImplementedError("AIClassifier is not implemented yet.")


class EmbeddingClassifier(Classifier):
    """Tier 1 classifier: kNN over feedback-derived embeddings.

    Confidence = vote share of the winning class among the top-K neighbors,
    weighted by source (feedback=1.0, pseudolabel=pseudo_weight).

    Uses its own `ml_min_confidence` threshold, decoupled from
    `defaults.min_confidence_for_proposal` (which governs the rules tier).
    The two tiers measure confidence differently and should not share a cutoff.
    """

    def __init__(
        self,
        rules_cfg: RulesConfig,
        embedder: Embedder,
        training_store: TrainingStore,
        *,
        organize_root: Optional[Union[str, Path]] = None,
        today_str: Optional[str] = None,
        extractor: Optional[ContentExtractor] = None,
        k: Optional[int] = None,
        pseudo_weight: Optional[float] = None,
        ml_min_confidence: Optional[float] = None,
    ) -> None:
        self.rules_cfg = rules_cfg
        self.embedder = embedder
        self.training_store = training_store
        self.extractor = extractor or SimpleContentExtractor()
        self.organize_root = (
            Path(organize_root).expanduser().resolve()
            if organize_root
            else (
                Path(rules_cfg.organize_root).expanduser().resolve()
                if rules_cfg.organize_root
                else None
            )
        )
        self.today_str = today_str
        # Read tuning from rules_cfg.ml (Stage 7); explicit kwargs win,
        # then config, then hardcoded fallbacks.
        ml_cfg = getattr(rules_cfg, "ml", None)
        self.k = k if k is not None else (ml_cfg.k if ml_cfg else 5)
        self.pseudo_weight = (
            pseudo_weight if pseudo_weight is not None
            else (ml_cfg.pseudo_weight if ml_cfg else 0.4)
        )
        self.ml_min_confidence = (
            ml_min_confidence if ml_min_confidence is not None
            else (ml_cfg.min_confidence_for_proposal if ml_cfg else 0.55)
        )

    def classify(self, record: FileRecord) -> Proposal:
        from organizer.rules.engine import compute_destination_path
        
        if self.training_store.is_empty():
            raise ClassifierUnavailable(
                "ml tier has no training data",
                hint="run 'organizer propose --model rules' first to seed bootstrap labels",
            )

        text = self.extractor.extract_content(record.path)
        if not text:
            return self._fallback(record, "ml: empty snippet, cannot embed")

        vec = np.asarray(self.embedder.generate_embedding(text), dtype=np.float32)

        # Pairwise cosine similarity against stored examples.
        # Embeddings are L2-normalized, so cosine == dot product.
        sims: list[tuple[float, str, str, str]] = []  # (sim, category, destination, source)
        for ex in self.training_store.examples:
            if ex.vector is None:
                continue
            sim = float(np.dot(vec, ex.vector))
            # Down-weight pseudo-labels so real feedback dominates the vote.
            if ex.source == "pseudolabel":
                sim *= self.pseudo_weight
            sims.append((sim, ex.category, ex.destination, ex.source))

        if not sims:
            return self._fallback(record, "ml: training examples have no vectors")

        sims.sort(key=lambda t: t[0], reverse=True)
        top_k = sims[: self.k]

        # Weighted vote by category.
        votes: dict[str, float] = {}
        dest_votes: dict[str, dict[str, float]] = {}
        for sim, category, destination, _src in top_k:
            votes[category] = votes.get(category, 0.0) + sim
            dest_votes.setdefault(category, {})
            dest_votes[category][destination] = dest_votes[category].get(destination, 0.0) + sim

        # Soft penalty on categories the user explicitly rejected in the past.
        for cat in list(votes.keys()):
            if cat in self.training_store.rejected_categories:
                votes[cat] *= 0.5

        total = sum(votes.values())
        if total <= 0:
            return self._fallback(record, "ml: all votes were zero")

        winning_cat = max(votes, key=votes.__getitem__)
        winning_conf = votes[winning_cat] / total

        # Rejected categories get penalized but if they still win, it's a real edge case.
        winning_dest = max(
            dest_votes[winning_cat], key=dest_votes[winning_cat].__getitem__
        )

        neighbor_count = sum(1 for _s, c, _d, _src in top_k if c == winning_cat)
        top_sim = top_k[0][0]
        rationale = (
            f"ml: {neighbor_count}/{len(top_k)} neighbors -> {winning_cat} "
            f"(top cos {top_sim:.2f})"
        )

        if winning_conf < self.ml_min_confidence:
            return self._fallback(
                record,
                f"ml: winning vote {winning_conf:.2f} below threshold "
                f"{self.ml_min_confidence:.2f} ({rationale})",
            )

        base_dir = self._base_dir(record)
        dest_path = compute_destination_path(
            base_dir,
            Path(winning_dest).name,
            record.filename,
            self.today_str,
        )

        return Proposal(
            file_id=record.id,
            source_path=record.path,
            proposed_category=winning_cat,
            proposed_destination=str(dest_path),
            confidence=winning_conf,
            rationale=rationale,
            status="pending",
        )

    def _base_dir(self, record: FileRecord) -> Path:
        if self.organize_root is not None:
            return self.organize_root
        return Path(record.path).parent

    def _fallback(self, record: FileRecord, reason: str) -> Proposal:
        from organizer.rules.engine import compute_destination_path
        base_dir = self._base_dir(record)
        dest = compute_destination_path(
            base_dir,
            self.rules_cfg.defaults.unmatched_destination,
            record.filename,
            self.today_str,
        )
        return Proposal(
            file_id=record.id,
            source_path=record.path,
            proposed_category=self.rules_cfg.defaults.unmatched_category,
            proposed_destination=str(dest),
            confidence=0.0,
            rationale=reason,
            status="pending",
        )