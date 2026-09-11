"""Placeholder AI embedder for Phase 2."""

from typing import Sequence

from organizer.ai.base import Embedder


class AIEmbedder(Embedder):
    """Placeholder vector embedder using embedding models."""

    def generate_embedding(self, text: str) -> Sequence[float]:
        raise NotImplementedError(
            "AIEmbedder is a placeholder for Phase 2 (Vector Embeddings & Semantic Similarity). "
            "Phase 1 uses exact SHA-256 deduplication and rule-based matching only."
        )
