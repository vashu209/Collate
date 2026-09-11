"""Feedback recorder capturing user corrections, approvals, and rejections for Phase 2 learning."""

from typing import Optional

from organizer.rules.models import FeedbackRecord, Proposal
from organizer.storage.repository import Repository


class FeedbackRecorder:
    """Logs user decisions (accept, reject, manual destination edit) into persistent storage."""

    def __init__(self, repository: Repository):
        self.repository = repository

    def record_decision(
        self,
        proposal: Proposal,
        action: str,  # 'approved', 'rejected', 'modified'
        actual_category: Optional[str] = None,
        actual_destination: Optional[str] = None,
    ) -> FeedbackRecord:
        """Record a feedback entry for a proposal.
        
        Args:
            proposal: The evaluated Proposal.
            action: 'approved', 'rejected', or 'modified'.
            actual_category: Category overridden by user if any.
            actual_destination: Destination path overridden by user if any.
            
        Returns:
            The saved FeedbackRecord.
        """
        record = FeedbackRecord(
            file_id=proposal.file_id,
            source_path=proposal.source_path,
            proposed_category=proposal.proposed_category,
            proposed_destination=proposal.proposed_destination,
            actual_category=actual_category or proposal.proposed_category,
            actual_destination=actual_destination or proposal.proposed_destination,
            action=action,
        )

        fb_id = self.repository.save_feedback(record)
        record.id = fb_id
        return record
