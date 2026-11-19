"""Pydantic schemas for the Autonomous File Organizer API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Status
# -----------------------------------------------------------------------------
class StatusSummary(BaseModel):
    total_files_scanned: int = 0
    proposals_pending: int = 0
    proposals_approved: int = 0
    proposals_rejected: int = 0
    proposals_executed: int = 0
    operations_completed: int = 0
    operations_rolled_back: int = 0
    operations_failed: int = 0
    feedback_records: int = 0
    latest_scan_root: Optional[str] = None


# -----------------------------------------------------------------------------
# Proposals
# -----------------------------------------------------------------------------
class ProposalItem(BaseModel):
    id: int
    file_id: Optional[int] = None
    source_path: str
    proposed_category: str
    proposed_destination: str
    confidence: float
    rationale: str
    status: str
    created_at: float


class ProposalsListResponse(BaseModel):
    proposals: List[ProposalItem]
    total: int


class ApproveProposalsRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, description="List of proposal IDs to approve")


class RejectProposalsRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, description="List of proposal IDs to reject")


class ItemExecutionResult(BaseModel):
    id: int
    success: bool
    status: str
    destination: Optional[str] = None
    error: Optional[str] = None


class ProposalExecutionResponse(BaseModel):
    results: List[ItemExecutionResult]
    succeeded: int
    failed: int


# -----------------------------------------------------------------------------
# Operations & Rollback
# -----------------------------------------------------------------------------
class OperationItem(BaseModel):
    id: int
    file_id: Optional[int] = None
    proposal_id: Optional[int] = None
    source_path: str
    destination_path: str
    checksum: str
    status: str
    timestamp: float
    rolled_back_at: Optional[float] = None
    has_conflict: bool = False
    conflict_type: Optional[str] = None
    conflict_message: Optional[str] = None


class OperationsListResponse(BaseModel):
    operations: List[OperationItem]
    total: int


class RollbackRequest(BaseModel):
    operation_id: Optional[int] = None
    operation_ids: Optional[List[int]] = None
    last_n: Optional[int] = None
    all_completed: bool = False


class RollbackItemResult(BaseModel):
    operation_id: int
    success: bool
    message: str
    restored_path: Optional[str] = None


class RollbackResponse(BaseModel):
    results: List[RollbackItemResult]
    succeeded: int
    failed: int


# -----------------------------------------------------------------------------
# Async Tasks (Scan / Propose)
# -----------------------------------------------------------------------------
class ScanRequest(BaseModel):
    path: str
    recursive: bool = True


class ProposeRequest(BaseModel):
    model: str = "rules"
    min_confidence: Optional[float] = None
    organize_root: Optional[str] = None
    no_fallback: bool = False


class TaskStatusResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: int = 0
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
