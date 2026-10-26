"""Map --model names to Classifier instances.

Everything downstream (CLI, storage, mover) stays ignorant of which tier
is running. The registry is the only place that knows about names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Union

from organizer.ai.base import Classifier, ClassifierUnavailable
from organizer.ai.capabilities import Capabilities, detect_capabilities
from organizer.config.schema import RulesConfig
from organizer.rules.engine import RuleBasedClassifier


# Register tiers here. Each entry is a lazy factory: it is only called when
# that tier is actually requested, so missing deps for one tier do not affect
# the others.
_FACTORIES: dict[str, Callable[..., Classifier]] = {}


def _build_rules(
    rules_cfg: RulesConfig,
    *,
    organize_root: Optional[Union[str, Path]] = None,
    today_str: Optional[str] = None,
    **_ignored,
) -> Classifier:
    return RuleBasedClassifier(
        rules_cfg,
        organize_root=organize_root,
        today_str=today_str,
    )


def _build_ml(
    rules_cfg: RulesConfig,
    *,
    organize_root: Optional[Union[str, Path]] = None,
    today_str: Optional[str] = None,
    **_ignored,
) -> Classifier:
    # Import here so that a missing onnxruntime/tokenizers only fails when
    # the user actually asks for --model ml. These land in Stages 2–4.
    try:
        from organizer.ai.classifier import EmbeddingClassifier
        from organizer.ai.embedder import AIEmbedder
        from organizer.ai.training_store import TrainingStore
    except ImportError as e:
        # Stage 1 safety net: any of these not yet written surfaces as a
        # clean "unavailable" rather than a crash. Stage 4 removes this guard.
        raise ClassifierUnavailable(
            f"ml tier not fully installed: {e}",
            hint="see DEVELOPER.md for the ML tier setup",
        ) from e

    embedder = AIEmbedder()
    store = TrainingStore()
    return EmbeddingClassifier(
        rules_cfg,
        embedder,
        store,
        organize_root=organize_root,
        today_str=today_str,
    )


_FACTORIES["rules"] = _build_rules
_FACTORIES["ml"] = _build_ml
# llm and api wired in later; absent keys are treated as "not implemented".


def available_models() -> list[str]:
    """Names that have a factory registered (regardless of install state)."""
    return sorted(_FACTORIES.keys())


def build_classifier(
    name: str,
    rules_cfg: RulesConfig,
    caps: Optional[Capabilities] = None,
    *,
    organize_root: Optional[Union[str, Path]] = None,
    today_str: Optional[str] = None,
    **kwargs,
) -> Classifier:
    """Instantiate the requested classifier.

    Raises ClassifierUnavailable if the tier is registered but not runnable
    on this machine, or if the name is unknown.
    """
    if name not in _FACTORIES:
        raise ClassifierUnavailable(
            f"unknown classifier: {name!r}",
            hint=f"available: {', '.join(available_models())}",
        )

    caps = caps or detect_capabilities()

    if not getattr(caps, name, False):
        reason = caps.reasons.get(name, "unavailable on this machine")
        raise ClassifierUnavailable(f"classifier {name!r} unavailable: {reason}")

    return _FACTORIES[name](
        rules_cfg,
        organize_root=organize_root,
        today_str=today_str,
        **kwargs,
    )