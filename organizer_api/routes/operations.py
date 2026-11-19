"""Operations and rollback endpoints."""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends

from organizer.dedup.hasher import compute_file_hash
from organizer.operations.rollback import RollbackManager, RollbackResult
from organizer.storage.repository import Repository
from organizer_api.dependencies import get_repo, get_rollback_manager
from organizer_api.models import (
    OperationItem,
    OperationsListResponse,
    RollbackItemResult,
    RollbackRequest,
    RollbackResponse,
)

router = APIRouter(tags=["operations"])


@router.get("/operations", response_model=OperationsListResponse)
def list_operations(
    limit: Optional[int] = 500,
    repo: Repository = Depends(get_repo),
) -> OperationsListResponse:
    """List completed operations with read-only conflict detection."""
    ops = repo.get_completed_operations(limit=limit)
    items: List[OperationItem] = []

    for op in ops:
        has_conflict = False
        conflict_type: Optional[str] = None
        conflict_message: Optional[str] = None

        dest = Path(op.destination_path)
        src = Path(op.source_path)

        # Conflict check 1: Destination file exists and matches hash
        if not dest.exists():
            has_conflict = True
            conflict_type = "missing_destination"
            conflict_message = f"File missing at destination: {dest.name}"
        else:
            try:
                dest_hash = compute_file_hash(dest)
                if dest_hash != op.checksum:
                    has_conflict = True
                    conflict_type = "file_modified"
                    conflict_message = "File was modified since move (checksum mismatch)"
            except Exception as e:
                has_conflict = True
                conflict_type = "read_error"
                conflict_message = f"Cannot read destination: {e}"

        # Conflict check 2: Original source path occupied by a different file
        if not has_conflict and src.exists():
            try:
                src_hash = compute_file_hash(src)
                if src_hash != op.checksum:
                    has_conflict = True
                    conflict_type = "source_occupied"
                    conflict_message = "Original path is occupied by a different file"
            except Exception as e:
                has_conflict = True
                conflict_type = "read_error"
                conflict_message = f"Cannot read source path: {e}"

        items.append(
            OperationItem(
                id=op.id or 0,
                file_id=op.file_id,
                proposal_id=op.proposal_id,
                source_path=op.source_path,
                destination_path=op.destination_path,
                checksum=op.checksum,
                status=op.status,
                timestamp=op.timestamp,
                rolled_back_at=op.rolled_back_at,
                has_conflict=has_conflict,
                conflict_type=conflict_type,
                conflict_message=conflict_message,
            )
        )

    return OperationsListResponse(operations=items, total=len(items))


@router.post("/rollback", response_model=RollbackResponse)
def execute_rollback(
    body: RollbackRequest,
    rollback_mgr: RollbackManager = Depends(get_rollback_manager),
) -> RollbackResponse:
    """Execute rollback for specified operation(s) or batch."""
    raw_results: List[RollbackResult] = []

    if body.operation_ids:
        for oid in body.operation_ids:
            raw_results.extend(rollback_mgr.rollback_batch(operation_id=oid))
    elif body.operation_id is not None:
        raw_results.extend(rollback_mgr.rollback_batch(operation_id=body.operation_id))
    elif body.last_n is not None and body.last_n > 0:
        raw_results.extend(rollback_mgr.rollback_batch(last_n=body.last_n))
    elif body.all_completed:
        raw_results.extend(rollback_mgr.rollback_batch(all_completed=True))

    results = [
        RollbackItemResult(
            operation_id=r.operation.id or 0,
            success=r.success,
            message=r.message,
            restored_path=r.restored_path,
        )
        for r in raw_results
    ]
    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded

    return RollbackResponse(results=results, succeeded=succeeded, failed=failed)
