"""Safe filesystem move operations with cross-filesystem integrity and pre-operation logging."""

import logging
import os
from pathlib import Path
import shutil
from typing import Optional, Tuple, Union

from organizer.dedup.hasher import compute_file_hash
from organizer.rules.models import Operation, Proposal
from organizer.storage.repository import Repository
from organizer.utils.paths import ensure_parent_directory, resolve_collision_free_path

logger = logging.getLogger(__name__)


class MoveError(Exception):
    """Raised when a safe move operation fails."""
    pass


class FileMover:
    """Safely executes file moves with collision avoidance, pre-logging, and SHA-256 verification."""

    def __init__(self, repository: Repository):
        self.repository = repository

    def execute_move(
        self,
        proposal: Proposal,
        allow_symlinks: bool = False,
        explicit_destination: Optional[Union[str, Path]] = None,
    ) -> Tuple[bool, Optional[Operation], Optional[str]]:
        """Execute a move for a given proposal following all safety constraints.
        
        Workflow:
            1. Validate source file exists and is accessible.
            2. Check symlink constraints (skip by default).
            3. Verify source SHA-256 checksum.
            4. Resolve collision-free destination path.
            5. Pre-log intended operation in database before touching filesystem.
            6. Copy to destination with metadata (shutil.copy2).
            7. Verify destination file SHA-256 matches source SHA-256.
            8. Safely remove source file.
            9. Mark operation 'completed' and update proposal 'executed'.
            
        Args:
            proposal: Approved Proposal to execute.
            allow_symlinks: Whether to allow moving symlinks (default False).
            explicit_destination: Optional user-edited destination override.
            
        Returns:
            Tuple of (success: bool, operation: Optional[Operation], error_message: Optional[str])
        """
        source_path = Path(proposal.source_path).resolve()

        # Step 1: Validate source existence
        if not source_path.exists():
            msg = f"Source file does not exist: {source_path}"
            logger.warning(msg)
            return False, None, msg

        # Step 2: Symlink safety
        if source_path.is_symlink() and not allow_symlinks:
            msg = f"Skipping symlink file: {source_path}"
            logger.info(msg)
            return False, None, msg

        # Step 3: Compute source checksum
        try:
            source_checksum = compute_file_hash(source_path)
        except (PermissionError, OSError) as e:
            msg = f"Permission or I/O error reading source {source_path}: {e}"
            logger.warning(msg)
            return False, None, msg

        # Step 4: Resolve destination path safely without collisions
        target_dest_str = explicit_destination or proposal.proposed_destination
        target_dest = Path(target_dest_str).expanduser().resolve()
        final_dest = resolve_collision_free_path(target_dest)

        try:
            ensure_parent_directory(final_dest)
        except (PermissionError, OSError) as e:
            msg = f"Failed to create parent directory for {final_dest}: {e}"
            logger.warning(msg)
            return False, None, msg

        # Step 5: Pre-log intended operation in DB before touching filesystem
        operation = Operation(
            file_id=proposal.file_id,
            proposal_id=proposal.id,
            source_path=str(source_path),
            destination_path=str(final_dest),
            checksum=source_checksum,
            status="pending",
        )
        op_id = self.repository.record_operation(operation)
        operation.id = op_id

        # Step 6 & 7: Safe copy -> checksum verify -> remove source
        dest_copied = False
        try:
            shutil.copy2(str(source_path), str(final_dest))
            dest_copied = True

            dest_checksum = compute_file_hash(final_dest)
            if dest_checksum != source_checksum:
                raise MoveError(
                    f"Checksum mismatch! Source: {source_checksum} vs Dest: {dest_checksum}"
                )

            # Step 8: Remove source file
            os.remove(str(source_path))

            # Step 9: Mark operation completed and proposal executed
            self.repository.update_operation_status(op_id, status="completed")
            operation.status = "completed"

            if proposal.id:
                self.repository.update_proposal_status(proposal.id, status="executed")
                proposal.status = "executed"

            logger.info(f"Successfully moved: {source_path} -> {final_dest}")
            return True, operation, None

        except Exception as e:
            err_msg = f"Move failed for {source_path} -> {final_dest}: {e}"
            logger.error(err_msg)

            # Cleanup incomplete destination copy if created
            if dest_copied and final_dest.exists():
                try:
                    os.remove(str(final_dest))
                except Exception as cleanup_err:
                    logger.warning(f"Failed to clean up destination {final_dest}: {cleanup_err}")

            self.repository.update_operation_status(op_id, status="failed", error_message=err_msg)
            operation.status = "failed"
            operation.error_message = err_msg
            return False, operation, err_msg
