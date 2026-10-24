"""Proposal engine re-exporting RuleBasedClassifier and destination calculation."""

from organizer.rules.engine import (
    RuleBasedClassifier,
    RuleEngine,
    compute_destination_path,
)

__all__ = [
    "RuleBasedClassifier",
    "RuleEngine",
    "compute_destination_path",
]
