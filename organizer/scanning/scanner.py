"""Filesystem scanner yielding FileRecord objects with metadata and checksums."""

import logging
import os
from pathlib import Path
from typing import Generator, Optional, Union

from organizer.dedup.hasher import compute_file_hash
from organizer.rules.models import FileRecord
from organizer.scanning.metadata import extract_metadata

logger = logging.getLogger(__name__)


def scan_directory(
    root_path: Union[str, Path],
    recursive: bool = True,
    skip_symlinks: bool = True,
    compute_hashes: bool = True,
) -> Generator[FileRecord, None, None]:
    """Walk a directory and yield FileRecord objects for all encountered files.
    
    Args:
        root_path: Directory path to scan.
        recursive: If True, recursively scan subdirectories.
        skip_symlinks: If True, do not traverse symlinks or include symlinked files.
        compute_hashes: If True, compute SHA-256 checksum for each file.
        
    Yields:
        FileRecord instances for accessible files.
    """
    base_path = Path(root_path).expanduser().resolve()
    if not base_path.exists():
        raise FileNotFoundError(f"Scan target path does not exist: {base_path}")
    if not base_path.is_dir():
        raise NotADirectoryError(f"Scan target path is not a directory: {base_path}")

    for root, dirnames, filenames in os.walk(base_path, followlinks=not skip_symlinks):
        current_dir = Path(root)

        # In non-recursive mode, clear dirnames so os.walk does not descend
        if not recursive and current_dir != base_path:
            dirnames.clear()
            continue

        # Prune symlinked directories if skipping symlinks
        if skip_symlinks:
            dirnames[:] = [d for d in dirnames if not (current_dir / d).is_symlink()]

        for fname in filenames:
            file_path = current_dir / fname

            try:
                is_link = file_path.is_symlink()
                if is_link and skip_symlinks:
                    logger.debug(f"Skipping symlink file: {file_path}")
                    continue

                size_bytes, created_at, modified_at, extension, mime_type, is_symlink = (
                    extract_metadata(file_path)
                )

                sha256: Optional[str] = None
                if compute_hashes and not is_symlink:
                    try:
                        sha256 = compute_file_hash(file_path)
                    except (PermissionError, OSError) as e:
                        logger.warning(f"Unable to read file for hashing {file_path}: {e}")
                        sha256 = None

                yield FileRecord(
                    path=str(file_path.resolve()),
                    filename=fname,
                    extension=extension,
                    size_bytes=size_bytes,
                    created_at=created_at,
                    modified_at=modified_at,
                    sha256=sha256,
                    mime_type=mime_type,
                    is_symlink=is_symlink,
                )
            except (PermissionError, OSError) as e:
                logger.warning(f"Error accessing file {file_path}: {e}")
                continue

        if not recursive:
            break
