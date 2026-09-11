"""Thin repository layer providing CRUD operations over SQLite."""

from pathlib import Path
import sqlite3
import time
from typing import Dict, List, Optional, Union

from organizer.rules.models import (
    FeedbackRecord,
    FileRecord,
    Operation,
    Proposal,
)
from organizer.storage.db import get_db_connection, init_db


class Repository:
    """Thin repository layer managing persistence of files, proposals, operations, and feedback."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path).resolve()
        # Ensure schema is initialized
        init_db(self.db_path)

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    # -------------------------------------------------------------------------
    # Files
    # -------------------------------------------------------------------------
    def upsert_file(self, record: FileRecord) -> int:
        """Insert or update a FileRecord. Returns the database row ID."""
        sql = """
        INSERT INTO files (
            path, filename, extension, size_bytes, created_at,
            modified_at, sha256, mime_type, is_symlink, scanned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            filename=excluded.filename,
            extension=excluded.extension,
            size_bytes=excluded.size_bytes,
            created_at=excluded.created_at,
            modified_at=excluded.modified_at,
            sha256=excluded.sha256,
            mime_type=excluded.mime_type,
            is_symlink=excluded.is_symlink,
            scanned_at=excluded.scanned_at
        RETURNING id;
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                sql,
                (
                    record.path,
                    record.filename,
                    record.extension,
                    record.size_bytes,
                    record.created_at,
                    record.modified_at,
                    record.sha256,
                    record.mime_type,
                    1 if record.is_symlink else 0,
                    record.scanned_at,
                ),
            )
            row = cursor.fetchone()
            file_id = row[0]
            record.id = file_id
            return file_id

    def get_file_by_id(self, file_id: int) -> Optional[FileRecord]:
        """Fetch a FileRecord by its ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            if not row:
                return None
            return self._row_to_file_record(row)

    def get_file_by_path(self, path: str) -> Optional[FileRecord]:
        """Fetch a FileRecord by its exact normalized path."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
            if not row:
                return None
            return self._row_to_file_record(row)

    def get_all_files(self, path_prefix: Optional[str] = None) -> List[FileRecord]:
        """Fetch all scanned files, optionally filtered by directory prefix."""
        with self._get_conn() as conn:
            if path_prefix:
                norm_prefix = str(Path(path_prefix).resolve()) + "%"
                rows = conn.execute(
                    "SELECT * FROM files WHERE path LIKE ? ORDER BY path",
                    (norm_prefix,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM files ORDER BY path").fetchall()
            return [self._row_to_file_record(r) for r in rows]

    def get_files_without_pending_proposals(self) -> List[FileRecord]:
        """Fetch files that do not currently have an active pending proposal."""
        sql = """
        SELECT f.* FROM files f
        WHERE NOT EXISTS (
            SELECT 1 FROM proposals p
            WHERE p.file_id = f.id AND p.status = 'pending'
        )
        ORDER BY f.id ASC;
        """
        with self._get_conn() as conn:
            rows = conn.execute(sql).fetchall()
            return [self._row_to_file_record(r) for r in rows]

    def get_duplicates(self, path_prefix: Optional[str] = None) -> Dict[str, List[FileRecord]]:
        """Find exact duplicate files grouped by sha256 checksum."""
        records = self.get_all_files(path_prefix=path_prefix)
        by_hash: Dict[str, List[FileRecord]] = {}
        for r in records:
            if r.sha256:
                by_hash.setdefault(r.sha256, []).append(r)
        return {h: group for h, group in by_hash.items() if len(group) > 1}

    def _row_to_file_record(self, row: sqlite3.Row) -> FileRecord:
        return FileRecord(
            id=row["id"],
            path=row["path"],
            filename=row["filename"],
            extension=row["extension"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            sha256=row["sha256"],
            mime_type=row["mime_type"],
            is_symlink=bool(row["is_symlink"]),
            scanned_at=row["scanned_at"],
        )

    # -------------------------------------------------------------------------
    # Proposals
    # -------------------------------------------------------------------------
    def save_proposal(self, proposal: Proposal) -> int:
        """Insert a new proposal. Returns the created proposal ID."""
        sql = """
        INSERT INTO proposals (
            file_id, source_path, proposed_category, proposed_destination,
            confidence, rationale, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id;
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                sql,
                (
                    proposal.file_id,
                    proposal.source_path,
                    proposal.proposed_category,
                    proposal.proposed_destination,
                    proposal.confidence,
                    proposal.rationale,
                    proposal.status,
                    proposal.created_at,
                ),
            )
            row = cursor.fetchone()
            proposal_id = row[0]
            proposal.id = proposal_id
            return proposal_id

    def get_pending_proposals(self) -> List[Proposal]:
        """Fetch all proposals in 'pending' status."""
        sql = "SELECT * FROM proposals WHERE status = 'pending' ORDER BY id ASC;"
        with self._get_conn() as conn:
            rows = conn.execute(sql).fetchall()
            return [self._row_to_proposal(r) for r in rows]

    def get_proposal_by_id(self, proposal_id: int) -> Optional[Proposal]:
        """Fetch a single proposal by ID."""
        sql = "SELECT * FROM proposals WHERE id = ?;"
        with self._get_conn() as conn:
            row = conn.execute(sql, (proposal_id,)).fetchone()
            if not row:
                return None
            return self._row_to_proposal(row)

    def update_proposal_status(self, proposal_id: int, status: str) -> None:
        """Update proposal status (e.g. approved, rejected, executed)."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE proposals SET status = ? WHERE id = ?",
                (status, proposal_id),
            )

    def _row_to_proposal(self, row: sqlite3.Row) -> Proposal:
        return Proposal(
            id=row["id"],
            file_id=row["file_id"],
            source_path=row["source_path"],
            proposed_category=row["proposed_category"],
            proposed_destination=row["proposed_destination"],
            confidence=row["confidence"],
            rationale=row["rationale"],
            status=row["status"],
            created_at=row["created_at"],
        )

    # -------------------------------------------------------------------------
    # Operations
    # -------------------------------------------------------------------------
    def record_operation(self, operation: Operation) -> int:
        """Log an executed or pending filesystem operation. Returns operation ID."""
        sql = """
        INSERT INTO operations (
            file_id, proposal_id, source_path, destination_path,
            checksum, status, timestamp, rolled_back_at, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id;
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                sql,
                (
                    operation.file_id,
                    operation.proposal_id,
                    operation.source_path,
                    operation.destination_path,
                    operation.checksum,
                    operation.status,
                    operation.timestamp,
                    operation.rolled_back_at,
                    operation.error_message,
                ),
            )
            row = cursor.fetchone()
            op_id = row[0]
            operation.id = op_id
            return op_id

    def update_operation_status(
        self,
        operation_id: int,
        status: str,
        rolled_back_at: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update status and attributes of an existing operation."""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE operations
                SET status = ?, rolled_back_at = ?, error_message = ?
                WHERE id = ?
                """,
                (status, rolled_back_at, error_message, operation_id),
            )

    def get_operation_by_id(self, operation_id: int) -> Optional[Operation]:
        """Fetch a single operation by ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM operations WHERE id = ?", (operation_id,)).fetchone()
            if not row:
                return None
            return self._row_to_operation(row)

    def get_completed_operations(self, limit: Optional[int] = None) -> List[Operation]:
        """Fetch completed operations available for rollback (ordered by most recent first)."""
        sql = "SELECT * FROM operations WHERE status = 'completed' ORDER BY timestamp DESC"
        params = []
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [self._row_to_operation(r) for r in rows]

    def _row_to_operation(self, row: sqlite3.Row) -> Operation:
        return Operation(
            id=row["id"],
            file_id=row["file_id"],
            proposal_id=row["proposal_id"],
            source_path=row["source_path"],
            destination_path=row["destination_path"],
            checksum=row["checksum"],
            status=row["status"],
            timestamp=row["timestamp"],
            rolled_back_at=row["rolled_back_at"],
            error_message=row["error_message"],
        )

    # -------------------------------------------------------------------------
    # Feedback
    # -------------------------------------------------------------------------
    def save_feedback(self, feedback: FeedbackRecord) -> int:
        """Log user correction or acceptance decision."""
        sql = """
        INSERT INTO feedback (
            file_id, source_path, proposed_category, proposed_destination,
            actual_category, actual_destination, action, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id;
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                sql,
                (
                    feedback.file_id,
                    feedback.source_path,
                    feedback.proposed_category,
                    feedback.proposed_destination,
                    feedback.actual_category,
                    feedback.actual_destination,
                    feedback.action,
                    feedback.timestamp,
                ),
            )
            row = cursor.fetchone()
            feedback_id = row[0]
            feedback.id = feedback_id
            return feedback_id

    # -------------------------------------------------------------------------
    # Status & Summary
    # -------------------------------------------------------------------------
    def get_status_summary(self) -> Dict[str, int]:
        """Compute summary statistics for status display."""
        with self._get_conn() as conn:
            total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

            proposals_counts = dict(
                conn.execute(
                    "SELECT status, COUNT(*) FROM proposals GROUP BY status"
                ).fetchall()
            )

            operations_counts = dict(
                conn.execute(
                    "SELECT status, COUNT(*) FROM operations GROUP BY status"
                ).fetchall()
            )

            feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

            return {
                "total_files_scanned": total_files,
                "proposals_pending": proposals_counts.get("pending", 0),
                "proposals_approved": proposals_counts.get("approved", 0),
                "proposals_rejected": proposals_counts.get("rejected", 0),
                "proposals_executed": proposals_counts.get("executed", 0),
                "operations_completed": operations_counts.get("completed", 0),
                "operations_rolled_back": operations_counts.get("rolled_back", 0),
                "operations_failed": operations_counts.get("failed", 0),
                "feedback_records": feedback_count,
            }
