"""SQLite database initialization, connection management, and schema migrations."""

from pathlib import Path
import sqlite3
from typing import Union


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at REAL NOT NULL,
    modified_at REAL NOT NULL,
    sha256 TEXT,
    mime_type TEXT,
    is_symlink INTEGER NOT NULL DEFAULT 0,
    scanned_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    source_path TEXT NOT NULL,
    proposed_category TEXT NOT NULL,
    proposed_destination TEXT NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_file_id ON proposals(file_id);

CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    proposal_id INTEGER REFERENCES proposals(id) ON DELETE SET NULL,
    source_path TEXT NOT NULL,
    destination_path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    timestamp REAL NOT NULL,
    rolled_back_at REAL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    source_path TEXT NOT NULL,
    proposed_category TEXT NOT NULL,
    proposed_destination TEXT NOT NULL,
    actual_category TEXT,
    actual_destination TEXT,
    action TEXT NOT NULL,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_action ON feedback(action);
"""


def get_db_connection(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Open an SQLite connection configured with WAL journal mode and foreign keys.
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        Configured sqlite3.Connection.
    """
    path = Path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Initialize database schema tables and indexes if not already present.
    
    Args:
        db_path: Path to the SQLite database file.
        
    Returns:
        Initialized sqlite3.Connection.
    """
    conn = get_db_connection(db_path)
    with conn:
        conn.executescript(SCHEMA_SQL)
    return conn
