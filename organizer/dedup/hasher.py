"""Exact-duplicate detection and SHA-256 hashing utilities."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Union

from organizer.rules.models import FileRecord


def compute_file_hash(file_path: Union[str, Path], chunk_size: int = 65536) -> str:
    """Compute SHA-256 checksum for a file using chunked streaming.
    
    Args:
        file_path: Path to the target file.
        chunk_size: Buffer size for reading chunks (default 64KB).
        
    Returns:
        Hex-encoded SHA-256 string.
    """
    hasher = hashlib.sha256()
    path = Path(file_path).resolve()

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


def find_duplicates(records: List[FileRecord]) -> Dict[str, List[FileRecord]]:
    """Group file records by SHA-256 checksum where duplicates exist.
    
    Args:
        records: List of FileRecord instances.
        
    Returns:
        Dictionary mapping SHA-256 checksums to lists of duplicate FileRecords (len > 1).
    """
    by_hash: Dict[str, List[FileRecord]] = {}
    for record in records:
        if not record.sha256:
            continue
        by_hash.setdefault(record.sha256, []).append(record)

    return {h: recs for h, recs in by_hash.items() if len(recs) > 1}
