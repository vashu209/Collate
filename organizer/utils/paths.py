"""Collision-safe destination path generation and filesystem path helpers."""

from pathlib import Path
from typing import Union


def resolve_collision_free_path(target_path: Union[str, Path]) -> Path:
    """Generate a collision-safe file path by appending a numeric suffix if needed.
    
    If the target file already exists, appends '_1', '_2', etc. before the extension
    to guarantee that existing files are never overwritten silently.
    
    Example:
        'report.pdf' -> 'report_1.pdf' -> 'report_2.pdf'
        
    Args:
        target_path: Desired destination file path.
        
    Returns:
        A Path guaranteed not to exist on the filesystem at the moment of evaluation.
    """
    path = Path(target_path).resolve()
    if not path.exists():
        return path

    parent = path.parent
    stem = path.stem
    suffix = path.suffix

    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def ensure_parent_directory(file_path: Union[str, Path]) -> Path:
    """Ensure the parent directory of a given file path exists.
    
    Args:
        file_path: Target file path.
        
    Returns:
        The Path instance.
    """
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
