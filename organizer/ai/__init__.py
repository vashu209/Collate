"""AI abstractions and placeholders for Phase 2."""

from organizer.ai.base import Classifier, ContentExtractor, Embedder
from organizer.ai.classifier import AIClassifier
from organizer.ai.content_extractor import SimpleContentExtractor
from organizer.ai.embedder import AIEmbedder

__all__ = [
    "Classifier",
    "ContentExtractor",
    "Embedder",
    "AIClassifier",
    "SimpleContentExtractor",
    "AIEmbedder",
]
