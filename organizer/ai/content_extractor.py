"""Extract a short text snippet from a file for embedding."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from organizer.ai.base import ContentExtractor

logger = logging.getLogger(__name__)

_MAX_TEXT_BYTES = 2048
_MAX_SNIPPET_CHARS = 512

_TEXT_EXTENSIONS = {
    "txt", "md", "rst", "log", "csv", "tsv",
    "py", "js", "ts", "tsx", "jsx", "go", "rs", "java", "c", "cpp", "h",
    "json", "yaml", "yml", "toml", "ini", "cfg", "conf", "xml", "html",
    "sh", "bash", "zsh", "sql",
}


class SimpleContentExtractor(ContentExtractor):
    """Build a snippet from filename, parent directory, and file body."""

    def __init__(self, max_chars: int = _MAX_SNIPPET_CHARS) -> None:
        self.max_chars = max_chars

    def extract_content(self, file_path: Union[str, Path]) -> str:
        path = Path(file_path)
        ext = path.suffix.lstrip(".").lower()
        parent = path.parent.name

        body = ""
        try:
            if ext in _TEXT_EXTENSIONS:
                body = self._read_text(path)
            elif ext == "pdf":
                body = self._read_pdf(path)
        except Exception as e:
            logger.debug("extraction failed for %s: %s", path, e)

        parts = [parent, path.name]
        if body:
            parts.append(body)
        snippet = " ".join(p for p in parts if p)
        return snippet[: self.max_chars]

    def _read_text(self, path: Path) -> str:
        with path.open("rb") as f:
            raw = f.read(_MAX_TEXT_BYTES)
        return raw.decode("utf-8", errors="replace").strip()

    def _read_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.debug("pypdf not installed; skipping PDF body for %s", path)
            return ""
        try:
            reader = PdfReader(str(path))
            if not reader.pages:
                return ""
            return (reader.pages[0].extract_text() or "").strip()
        except Exception as e:
            logger.debug("pdf read failed for %s: %s", path, e)
            return ""