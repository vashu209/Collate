"""Load labeled examples from user feedback for kNN classification."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from organizer.ai.content_extractor import SimpleContentExtractor
from organizer.ai.base import Embedder             # one for type
from organizer.ai.embedder import AIEmbedder       # other for default instance
from organizer.storage.repository import Repository

logger = logging.getLogger(__name__)


@dataclass
class TrainingExample:
    """One labeled example: text, category, destination parent, and source."""
    text: str
    category: str
    destination: str
    source: str  # "feedback" or "pseudolabel"
    file_id: Optional[int] = None  # NEW: required for safe self-exclusion
    vector: Optional[np.ndarray] = None


class TrainingStore:
    """Loads feedback rows, embeds their content, and keeps vectors in memory.

    Sources:
      - feedback: real user decisions (action in approved/modified)
      - pseudolabel: rules-engine proposals added via add_pseudolabels() for cold start

    Rejected feedback is stored as `rejected_categories` (used to nudge votes away).
    """

    def __init__(
        self,
        repository: Optional[Repository] = None,
        embedder: Optional[Embedder] = None,
        extractor: Optional[SimpleContentExtractor] = None,
    ) -> None:
        self.repository = repository
        self.embedder = embedder or AIEmbedder()
        self.extractor = extractor or SimpleContentExtractor()
        self.examples: List[TrainingExample] = []
        self.rejected_categories: set[str] = set()
        self._loaded = False

    def load(self) -> int:
        """Load feedback rows and embed them. Returns example count."""
        self.examples = []
        self.rejected_categories = set()
        self._loaded = True

        if self.repository is None:
            return 0

        rows = self.repository.get_feedback()
        for row in rows:
            category = row.actual_category or row.proposed_category

            if row.action == "rejected":
                self.rejected_categories.add(category)
                continue
            if row.action not in ("approved", "modified"):
                continue

            # 1. Read the saved snippet directly from the DB
            text = getattr(row, "content_snippet", None)
            
            # Fallback: if this is an old row before the DB update, try to read the file
            # (This keeps backwards compatibility with your existing test DB)
            if not text:
                source_path = Path(row.source_path)
                if source_path.exists():
                    text = self.extractor.extract_content(source_path)
            
            # If we still have no text, skip it
            if not text:
                continue

            # 2. Read the saved category folder name
            dest_folder = getattr(row, "category_folder_name", None)
            
            # Fallback: if old row, extract the name, but strip the date bucket if present
            if not dest_folder:
                logger.debug("Skipping old feedback row without category_folder_name")
                continue

            self.examples.append(
                TrainingExample(
                    text=text,
                    category=category,
                    destination=dest_folder,  # Now strictly the folder name!
                    source="feedback",
                    file_id=row.file_id,
                )
            )

            if self.examples:
                self._embed_examples()

            logger.info(
                "TrainingStore loaded: %d examples, %d rejected categories",
                len(self.examples),
                len(self.rejected_categories),
            )
            return len(self.examples)

    def add_pseudolabels(self, triples: List[Tuple[int,str, str, str]]) -> int:
        """Seed from rules-engine output: (text, category, destination_parent)."""
        added = 0
        for file_id, text, category, dest in triples:
            if not text:
                continue
            self.examples.append(
                TrainingExample(
                    text=text,
                    category=category,
                    destination=dest,
                    source="pseudolabel",
                    file_id=file_id,
                )
            )
            added += 1
        if added:
            self._embed_examples()
        return added

    def _embed_examples(self) -> None:
        """Batch-embed every example missing a vector."""
        pending = [ex for ex in self.examples if ex.vector is None]
        if not pending:
            return

        texts = [ex.text for ex in pending]
        vectors = self.embedder.encode_batch(texts)
        for ex, vec in zip(pending, vectors):
            ex.vector = np.asarray(vec, dtype=np.float32)

    def is_empty(self) -> bool:
        return not self.examples