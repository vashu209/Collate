"""Detect which classifier tiers can run on the current machine.

All checks are import-time or filesystem-only. Nothing here loads a model,
opens a network connection, or imports a heavy dependency. Safe to call
from `organizer --help`.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Capabilities:
    rules: bool = True
    ml: bool = False
    llm: bool = False
    api: bool = False
    reasons: dict[str, str] = field(default_factory=dict)


def _module_available(name: str) -> bool:
    """True if a top-level module can be found without importing it."""
    return importlib.util.find_spec(name) is not None


def _ml_model_dir() -> Path | None:
    """Resolve the MiniLM model directory if it exists.

    Order:
      1. ORGANIZER_ML_MODEL_DIR env var (user override).
      2. Shipped package data at organizer/ai/models/minilm-l6-v2/.
    """
    env = os.environ.get("ORGANIZER_ML_MODEL_DIR")
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_dir() else None

    shipped = Path(__file__).parent / "models" / "minilm-l6-v2"
    return shipped if shipped.is_dir() else None


def _ml_available() -> tuple[bool, str]:
    """Check ML tier prerequisites. Returns (ok, reason)."""
    missing = []
    for mod in ("onnxruntime", "tokenizers", "numpy"):
        if not _module_available(mod):
            missing.append(mod)
    if missing:
        return (
            False,
            f"missing modules: {', '.join(missing)}; "
            "install with 'pip install file-organizer[ml]'",
        )

    model_dir = _ml_model_dir()
    if model_dir is None:
        return False, "MiniLM model files not found; run scripts/fetch_ml_model.py"

    # Sanity: tokenizer.json and model.onnx must be present.
    for fname in ("model.onnx", "tokenizer.json"):
        if not (model_dir / fname).exists():
            return False, f"model dir missing {fname}: {model_dir}"

    return True, ""


def _llm_available() -> tuple[bool, str]:
    """Stub for Tier 2. Always false for now."""
    return False, "Tier 2 (local LLM) not implemented yet"


def _api_available() -> tuple[bool, str]:
    """Stub for Tier 3. Always false for now."""
    return False, "Tier 3 (cloud API) not implemented yet"


def detect_capabilities() -> Capabilities:
    """Probe every tier and return the result set.

    Never raises. Failure modes are reported via `reasons` so the CLI can
    explain why a tier is grayed out.
    """
    reasons: dict[str, str] = {}

    ml_ok, ml_reason = _ml_available()
    if not ml_ok:
        reasons["ml"] = ml_reason

    llm_ok, llm_reason = _llm_available()
    if not llm_ok:
        reasons["llm"] = llm_reason

    api_ok, api_reason = _api_available()
    if not api_ok:
        reasons["api"] = api_reason

    return Capabilities(
        rules=True,
        ml=ml_ok,
        llm=llm_ok,
        api=api_ok,
        reasons=reasons,
    )