"""Proposals management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends

from organizer.feedback.recorder import FeedbackRecorder
from organizer.operations.mover import FileMover
from organizer.rules.models import Proposal
from organizer.storage.repository import Repository
from organizer_api.dependencies import get_mover, get_recorder, get_repo
from organizer_api.models import (
    ApproveProposalsRequest,
    ItemExecutionResult,
    ProposalExecutionResponse,
    ProposalItem,
    ProposalsListResponse,
    RejectProposalsRequest,
)

router = APIRouter(tags=["proposals"])


@router.get("/proposals", response_model=ProposalsListResponse)
def list_proposals(
    status: Optional[str] = "pending",
    category: Optional[str] = None,
    min_conf: Optional[float] = None,
    repo: Repository = Depends(get_repo),
) -> ProposalsListResponse:
    """List proposals with optional filters on status, category, and minimum confidence."""
    sql = "SELECT * FROM proposals WHERE 1=1"
    params: List[object] = []

    if status and status.lower() != "all":
        sql += " AND status = ?"
        params.append(status.lower())

    if category:
        sql += " AND LOWER(proposed_category) = LOWER(?)"
        params.append(category)

    if min_conf is not None:
        sql += " AND confidence >= ?"
        params.append(min_conf)

    sql += " ORDER BY confidence DESC, id ASC"

    with repo._get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        proposals = [repo._row_to_proposal(r) for r in rows]

    items = [
        ProposalItem(
            id=p.id or 0,
            file_id=p.file_id,
            source_path=p.source_path,
            proposed_category=p.proposed_category,
            proposed_destination=p.proposed_destination,
            confidence=p.confidence,
            rationale=p.rationale,
            status=p.status,
            created_at=p.created_at,
        )
        for p in proposals
    ]
    return ProposalsListResponse(proposals=items, total=len(items))


@router.post("/proposals/approve", response_model=ProposalExecutionResponse)
def approve_proposals(
    body: ApproveProposalsRequest,
    repo: Repository = Depends(get_repo),
    mover: FileMover = Depends(get_mover),
    recorder: FeedbackRecorder = Depends(get_recorder),
) -> ProposalExecutionResponse:
    """Approve selected proposals and execute their moves safely."""
    results: List[ItemExecutionResult] = []
    succeeded = 0
    failed = 0

    for pid in body.ids:
        proposal = repo.get_proposal_by_id(pid)
        if not proposal:
            results.append(
                ItemExecutionResult(id=pid, success=False, status="not_found", error="Proposal not found")
            )
            failed += 1
            continue

        if proposal.status != "pending":
            results.append(
                ItemExecutionResult(
                    id=pid, success=False, status=proposal.status, error=f"Proposal already {proposal.status}"
                )
            )
            failed += 1
            continue

        success, op, err = mover.execute_move(proposal)
        if success:
            recorder.record_decision(
                proposal,
                action="approved",
                actual_destination=op.destination_path if op else None,
            )
            results.append(
                ItemExecutionResult(
                    id=pid,
                    success=True,
                    status="executed",
                    destination=op.destination_path if op else None,
                )
            )
            succeeded += 1
        else:
            results.append(
                ItemExecutionResult(id=pid, success=False, status="failed", error=err or "Move failed")
            )
            failed += 1

    return ProposalExecutionResponse(results=results, succeeded=succeeded, failed=failed)


@router.post("/proposals/reject", response_model=ProposalExecutionResponse)
def reject_proposals(
    body: RejectProposalsRequest,
    repo: Repository = Depends(get_repo),
    recorder: FeedbackRecorder = Depends(get_recorder),
) -> ProposalExecutionResponse:
    """Reject selected proposals and record user feedback."""
    results: List[ItemExecutionResult] = []
    succeeded = 0
    failed = 0

    for pid in body.ids:
        proposal = repo.get_proposal_by_id(pid)
        if not proposal:
            results.append(
                ItemExecutionResult(id=pid, success=False, status="not_found", error="Proposal not found")
            )
            failed += 1
            continue

        if proposal.status != "pending":
            results.append(
                ItemExecutionResult(
                    id=pid, success=False, status=proposal.status, error=f"Proposal already {proposal.status}"
                )
            )
            failed += 1
            continue

        repo.update_proposal_status(proposal.id, "rejected")
        proposal.status = "rejected"
        recorder.record_decision(proposal, action="rejected")
        results.append(ItemExecutionResult(id=pid, success=True, status="rejected"))
        succeeded += 1

    return ProposalExecutionResponse(results=results, succeeded=succeeded, failed=failed)
