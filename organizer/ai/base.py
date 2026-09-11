"""Abstract base classes and interfaces for AI components (Phase 2 readiness)."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence, Union

from organizer.rules.models import FileRecord, Proposal


class ContentExtractor(ABC):
    """Interface for extracting text or semantic representation from file contents."""

    @abstractmethod
    def extract_content(self, file_path: Union[str, Path]) -> str:
        """Extract text or document representation from a file.
        
        Args:
            file_path: Path to the target file.
            
        Returns:
            Extracted text content.
        """
        pass


class Embedder(ABC):
    """Interface for generating semantic vector embeddings."""

    @abstractmethod
    def generate_embedding(self, text: str) -> Sequence[float]:
        """Generate a dense vector embedding from text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Vector embedding as a sequence of floats.
        """
        pass


class Classifier(ABC):
    """Interface for classifying a file record into an organization Proposal.
    
    Both RuleBasedClassifier (Phase 1) and AIClassifier (Phase 2)
    implement this identical contract.
    """

    @abstractmethod
    def classify(self, record: FileRecord) -> Proposal:
        """Evaluate a file record and produce an organization proposal.
        
        Args:
            record: The scanned file record with metadata.
            
        Returns:
            A Proposal containing category, destination, confidence, and rationale.
        """
        pass
