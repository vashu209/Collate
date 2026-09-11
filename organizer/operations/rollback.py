"""Rollback manager reversing logged operations and restoring files to original paths."""

import logging
import os
from pathlib import Path
import shutil
import time
from typing import List, Optional, Tuple

from organizer.dedup.hasher import compute_file_hash
from organizer.rules.models import Operation
from organizer.storage.repository import Repository
from organizer.utils.paths import ensure_parent_directory

logger = logging.getLogger(__name__)


class RollbackResult:
    """Outcome of an individual operation rollback."""

    def __init__(
        self,
        operation: Operation,
        success: bool,
        message: str,
        restored_path: Optional[str] = None,
    ):
        self.operation = operation
        self.success = success
        self.message = message
        self.restored_path = restored_path


class RollbackManager:
    """Manages reversing completed file move operations."""

    def __init__(self, repository: Repository):
        self.repository = repository

    def rollback_operation(self, operation: Operation) -> RollbackResult:
        """Roll back a single completed operation.
        
        Workflow:
            1. Verify current file exists at destination_path.
            2. Verify current file checksum matches operation checksum.
            3. Verify source_path does not have an unexpected conflicting file.
            4. Copy destination -> source.
            5. Verify restored source checksum.
            6. Delete destination file.
            7. Mark operation 'rolled_back' in database.
        """
        dest_path = Path(operation.destination_path).resolve()
        source_path = Path(operation.source_path).resolve()

        if not dest_path.exists():
            msg = f"Cannot rollback: File missing at destination: {dest_path}"
            logger.warning(msg)
            return RollbackResult(operation, False, msg)

        # Verify integrity at destination
        try:
            current_dest_hash = compute_file_hash(dest_path)
            if current_dest_hash != operation.checksum:
                msg = (
                    f"Integrity check failed: File at {dest_path} was modified "
                    f"(hash {current_dest_hash[:8]} != original {operation.checksum[:8]}). Refusing to rollback."
                )
                logger.error(msg)
                return RollbackResult(operation, False, msg)
        except Exception as e:
            msg = f"Failed to verify destination checksum at {dest_path}: {e}"
            return RollbackResult(operation, False, msg)

        # Check if source path is already occupied by a different file
        if source_path.exists():
            try:
                existing_source_hash = compute_file_hash(source_path)
                if existing_source_hash == operation.checksum:
                    # File already restored, just remove dest if different path
                    if dest_path != source_path:
                        os.remove(str(dest_path))
                    self._mark_rolled_back(operation)
                    return RollbackResult(
                        operation, True, "File already present at source with identical hash", str(source_path)
                    )
                else:
                    msg = f"Conflict: Different file already exists at source path {source_path}."
                    return RollbackResult(operation, False, msg)
            except Exception as e:
                msg = f"Error inspecting conflicting file at {source_path}: {e}"
                return RollbackResult(operation, False, msg)

        # Re-create source directory structure
        try:
            ensure_parent_directory(source_path)
        except Exception as e:
            msg = f"Failed to create parent directory for {source_path}: {e}"
            return RollbackResult(operation, False, msg)

        # Copy back to source, verify, and remove destination
        try:
            shutil.copy2(str(dest_path), str(source_path))
            restored_hash = compute_file_hash(source_path)
            if restored_hash != operation.checksum:
                # Cleanup incomplete source file
                if source_path.exists():
                    os.remove(str(source_path))
                msg = f"Checksum mismatch after restoring to {source_path}."
                return RollbackResult(operation, False, msg)

            os.remove(str(dest_path))
            self._mark_rolled_back(operation)
            logger.info(f"Successfully rolled back: {dest_path} -> {source_path}")
            return RollbackResult(
                operation, True, f"Restored {dest_path.name} to {source_path}", str(source_path)
            )
        except Exception as e:
            msg = f"Failed to restore {dest_path} to {source_path}: {e}"
            logger.error(msg)
            return RollbackResult(operation, False, msg)

    def _mark_rolled_back(self, operation: Operation) -> None:
        now = time.time()
        operation.status = "rolled_back"
        operation.rolled_back_at = now
        if operation.id:
            self.repository.update_operation_status(
                operation.id, status="rolled_back", rolled_back_at=now
            )

    def rollback_batch(
        self,
        last_n: Optional[int] = None,
        operation_id: Optional[int] = None,
        all_completed: bool = False,
    ) -> List[RollbackResult]:
        """Roll back a collection of completed operations.
        
        Args:
            last_n: Number of most recent operations to roll back.
            operation_id: Specific operation ID to roll back.
            all_completed: If True, roll back all completed operations.
            
        Returns:
            List of RollbackResults.
        """
        operations_to_rollback: List[Operation] = []

        if operation_id is not None:
            op = self.repository.get_operation_by_id(operation_id)
            if op and op.status == "completed":
                operations_to_rollback.append(op)
            elif op and op.status != "completed":
                logger.warning(f"Operation #{operation_id} has status '{op.status}', cannot rollback.")
            else:
                logger.warning(f"Operation #{operation_id} not found.")

        elif last_n is not None and last_n > 0:
            operations_to_rollback = self.repository.get_completed_operations(limit=last_n)

        elif all_completed:
            operations_to_rollback = self.repository.get_completed_operations()

        results = []
        for op in operations_to_rollback:
            results.append(self.rollback_operation(op))

        return results
