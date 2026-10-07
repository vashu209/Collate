"""Metadata extraction utilities including size, timestamps, and magic bytes."""

import mimetypes
from pathlib import Path
from typing import Optional, Tuple, Union
import filetype


def extract_metadata(file_path: Union[str, Path]) -> Tuple[int, float, float, str, Optional[str], bool]:
    """Extract filesystem metadata and magic-byte type for a file.
    
    Args:
        file_path: Absolute or relative path to the file.
        
    Returns:
        Tuple containing:
            - size_bytes (int)
            - created_at (float epoch)
            - modified_at (float epoch)
            - extension (str, lowercase without leading dot, e.g. 'pdf')
            - mime_type (Optional[str])
            - is_symlink (bool)
    """
    path = Path(file_path).resolve()
    is_symlink = path.is_symlink()

    # Use lstat if symlink to avoid following, stat otherwise
    stat_info = path.lstat() if is_symlink else path.stat()
    size_bytes = stat_info.st_size

    # Creation time: st_birthtime on macOS/BSD, st_ctime on Windows, fallback st_mtime
    created_at = getattr(stat_info, "st_birthtime", stat_info.st_ctime)
    modified_at = stat_info.st_mtime

    # Extension without leading dot, lowercased
    suffix = path.suffix.lower()
    extension = suffix.lstrip(".") if suffix else ""

    # Magic-byte detection via pure-python filetype
    mime_type: Optional[str] = None
    if not is_symlink and path.is_file() and size_bytes > 0:
        try:
            kind = filetype.guess(str(path))
            if kind is not None:
                mime_type = kind.mime
        except Exception:
            # Fallback if file reading fails
            mime_type = None

    # Fallback to standard library mimetypes if magic-byte detection returned None
    if mime_type is None and extension:
        guessed_type, _ = mimetypes.guess_type(str(path))
        if guessed_type:
            mime_type = guessed_type

    return size_bytes, float(created_at), float(modified_at), extension, mime_type, is_symlink
