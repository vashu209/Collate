"""Core domain models for files, rules, proposals, and operations."""

from dataclasses import dataclass, field
import time
from typing import Optional


@dataclass
class FileRecord:
    """Represents a scanned file on the filesystem with extracted metadata."""
    path: str
    filename: str
    extension: str
    size_bytes: int
    created_at: float
    modified_at: float
    id: Optional[int] = None
    sha256: Optional[str] = None
    mime_type: Optional[str] = None
    is_symlink: bool = False
    scanned_at: float = field(default_factory=time.time)


@dataclass
class Condition:
    """A match condition within a rule."""
    type: str  # 'extension', 'keyword_in_name', 'path_contains'
    values: list[str]
    confidence: float


@dataclass
class Rule:
    """A categorized classification rule with priority and match conditions."""
    name: str
    priority: int
    destination: str
    match_any: list[Condition]


@dataclass
class RuleMatch:
    """Information about a successful rule match against a file."""
    category: str
    destination: str
    priority: int
    confidence: float
    matched_condition_type: str
    matched_value: str
    rationale: str


@dataclass
class Proposal:
    """Proposed organization decision for a file.
    
    Serves as the stable contract between classification (rules or AI)
    and downstream approval/execution.
    """
    source_path: str
    proposed_category: str
    proposed_destination: str
    confidence: float
    rationale: str
    id: Optional[int] = None
    file_id: Optional[int] = None
    status: str = "pending"  # pending, approved, rejected, executed
    created_at: float = field(default_factory=time.time)


@dataclass
class Operation:
    """Log record of an executed filesystem operation, allowing reversal."""
    source_path: str
    destination_path: str
    checksum: str
    id: Optional[int] = None
    file_id: Optional[int] = None
    proposal_id: Optional[int] = None
    status: str = "completed"  # pending, completed, rolled_back, failed
    timestamp: float = field(default_factory=time.time)
    rolled_back_at: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class FeedbackRecord:
    """User review feedback record for learning and analytics."""
    source_path: str
    proposed_category: str
    proposed_destination: str
    action: str  # approved, rejected, modified
    id: Optional[int] = None
    file_id: Optional[int] = None
    actual_category: Optional[str] = None
    actual_destination: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
