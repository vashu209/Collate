"""Classifier implementations. EmbeddingClassifier is Tier 1."""

from __future__ import annotations

import logging
import os
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
    """Tier 1 classifier: kNN over feedback-derived embeddings."""

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
        ml_min_top_similarity: Optional[float] = None,
    ) -> None:
        self.rules_cfg = rules_cfg
        self.embedder = embedder
        self.training_store = training_store
        self.extractor = extractor or SimpleContentExtractor()
        self.organize_root = (
            Path(organize_root).expanduser().resolve() if organize_root
            else (Path(rules_cfg.organize_root).expanduser().resolve() if rules_cfg.organize_root else None)
        )
        self.today_str = today_str
        
        ml_cfg = getattr(rules_cfg, "ml", None)
        self.k = k if k is not None else (ml_cfg.k if ml_cfg else 5)
        self.pseudo_weight = pseudo_weight if pseudo_weight is not None else (ml_cfg.pseudo_weight if ml_cfg else 0.4)
        self.ml_min_confidence = ml_min_confidence if ml_min_confidence is not None else (ml_cfg.min_confidence_for_proposal if ml_cfg else 0.55)
        self.ml_min_top_similarity = ml_min_top_similarity if ml_min_top_similarity is not None else (getattr(ml_cfg, 'min_top_similarity', 0.35) if ml_cfg else 0.35)

        # Matrix caching
        self._matrix: Optional[np.ndarray] = None
        self._weights: Optional[np.ndarray] = None
        self._file_ids: Optional[List[Optional[int]]] = None
        self._sources: Optional[List[str]] = None
        self._categories: Optional[List[str]] = None
        self._destinations: Optional[List[str]] = None

    def _ensure_matrix(self) -> None:
        """Build or rebuild the stacked matrix if the store has changed."""
        if self._matrix is not None and self._file_ids is not None and len(self._file_ids) == len(self.training_store.examples):
            return  # Assume no change if length matches for now (can be improved with a hash)
        
        examples = [ex for ex in self.training_store.examples if ex.vector is not None]
        if not examples:
            self._matrix = np.empty((0, 384), dtype=np.float32)
            self._weights = np.empty(0, dtype=np.float32)
            self._file_ids = []
            self._categories = []
            self._destinations = []
            return

        self._matrix = np.vstack([ex.vector for ex in examples])
        self._weights = np.array([self.pseudo_weight if ex.source == "pseudolabel" else 1.0 for ex in examples], dtype=np.float32)
        self._file_ids = [ex.file_id for ex in examples]
        self._sources = [ex.source for ex in examples]
        self._categories = [ex.category for ex in examples]
        self._destinations = [ex.destination for ex in examples]

    def classify(self, record: FileRecord) -> Proposal:
        from organizer.rules.engine import compute_destination_path
        
        if self.training_store.is_empty():
            raise ClassifierUnavailable(
                "ml tier has no training data",
                hint="run 'organizer propose --model rules' first to seed bootstrap labels",
            )

        self._ensure_matrix()
        if self._matrix is None or self._matrix.shape[0] == 0:
            return self._fallback(record, "ml: no valid vectors in training store")

        text = self.extractor.extract_content(record.path)
        vec = np.asarray(self.embedder.generate_embedding(text), dtype=np.float32)

        # 1. Compute raw similarities
        raw_sims = self._matrix @ vec
        raw_sims = np.clip(raw_sims, 0.0, 1.0)

        # 2. Apply mask for self-exclusion (only pseudolabels)
        if record.id is not None:
            for i, (fid, src) in enumerate(zip(self._file_ids, self._sources)):
                if fid is not None and fid == record.id and src == "pseudolabel":
                    raw_sims[i] = 0.0 # Zero out masked entries so they can't pass the floor

        
        # 3. Apply weights and mask
        weighted_sims = raw_sims * self._weights

        # 4. Top K
        top_indices = np.argsort(weighted_sims)[-self.k:][::-1]
        if len(top_indices) == 0:
            return self._fallback(record, "ml: no neighbors after mask")

        # 5. Floor check on RAW similarity, not weighted
        top_raw_sim = np.max(raw_sims[top_indices])
        if top_raw_sim < self.ml_min_top_similarity:
            return self._fallback(record, f"ml: top raw similarity {top_raw_sim:.2f} below absolute threshold")

        votes: dict[str, float] = {}
        dest_votes: dict[str, dict[str, float]] = {}
        for idx in top_indices:
            w_sim = float(weighted_sims[idx])
            cat = self._categories[idx]
            dest = self._destinations[idx]
            votes[cat] = votes.get(cat, 0.0) + w_sim
            dest_votes.setdefault(cat, {})
            dest_votes[cat][dest] = dest_votes[cat].get(dest, 0.0) + w_sim

        total = sum(votes.values())
        if total <= 0:
            return self._fallback(record, "ml: all votes were zero")


       # 6. Penalty: Penalize votes, but divide by unpenalized total
        # This ensures a rejected category maxes out at 0.5 confidence (fails the 0.55 threshold)
        penalized_votes = {k: v for k, v in votes.items()}
        for cat in penalized_votes:
            if cat in self.training_store.rejected_categories:
                penalized_votes[cat] *= 0.5

        winning_cat = max(penalized_votes, key=penalized_votes.__getitem__)
        winning_conf = penalized_votes[winning_cat] / total

        winning_dest = max(dest_votes[winning_cat], key=dest_votes[winning_cat].__getitem__)
        neighbor_count = sum(1 for idx in top_indices if self._categories[idx] == winning_cat)
        
        rationale = f"ml: {neighbor_count}/{len(top_indices)} neighbors -> {winning_cat} (top raw cos {top_raw_sim:.2f})"

        if winning_conf < self.ml_min_confidence:
            return self._fallback(record, f"ml: winning vote {winning_conf:.2f} below threshold {self.ml_min_confidence:.2f} ({rationale})")

        # 7. PATH SANITIZATION
        # Allow nested folders (Work/Projects), but reject absolute paths and ..
        dest_path_obj = Path(winning_dest)
        if dest_path_obj.is_absolute() or ".." in dest_path_obj.parts:
            return self._fallback(record, f"ml: unsafe destination path '{winning_dest}'")

        base_dir = self._base_dir(record)
        dest_path = compute_destination_path(base_dir, winning_dest, record.filename, self.today_str)

        # 8. Final assertion that we didn't escape the root (resolving symlinks)
        try:
            dest_path.resolve().relative_to(base_dir.resolve())
        except ValueError:
            return self._fallback(record, "ml: path traversal detected")

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
            base_dir, self.rules_cfg.defaults.unmatched_destination, record.filename, self.today_str
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