"""Status endpoint."""

from fastapi import APIRouter, Depends

from organizer.storage.repository import Repository
from organizer_api.dependencies import get_repo
from organizer_api.models import StatusSummary

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusSummary)
def get_status(repo: Repository = Depends(get_repo)) -> StatusSummary:
    """Fetch current system statistics and status summary."""
    summary = repo.get_status_summary()
    latest_root = repo.get_latest_scan_root()
    return StatusSummary(
        total_files_scanned=summary.get("total_files_scanned", 0),
        proposals_pending=summary.get("proposals_pending", 0),
        proposals_approved=summary.get("proposals_approved", 0),
        proposals_rejected=summary.get("proposals_rejected", 0),
        proposals_executed=summary.get("proposals_executed", 0),
        operations_completed=summary.get("operations_completed", 0),
        operations_rolled_back=summary.get("operations_rolled_back", 0),
        operations_failed=summary.get("operations_failed", 0),
        feedback_records=summary.get("feedback_records", 0),
        latest_scan_root=latest_root,
    )
