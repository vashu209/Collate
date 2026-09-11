"""Placeholder AI content extractor for Phase 2."""

from pathlib import Path
from typing import Union

from organizer.ai.base import ContentExtractor


class AIContentExtractor(ContentExtractor):
    """Placeholder content extractor using semantic/NLP extraction."""

    def extract_content(self, file_path: Union[str, Path]) -> str:
        raise NotImplementedError(
            "AIContentExtractor is a placeholder for Phase 2 (Multimodal/NLP Content Extraction). "
            "Phase 1 uses deterministic metadata and magic-byte detection only."
        )
