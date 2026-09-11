"""Deduplication and hashing package."""

from organizer.dedup.hasher import compute_file_hash, find_duplicates

__all__ = ["compute_file_hash", "find_duplicates"]
