"""Core propose pipeline: model resolution, cold-start bootstrap, classification.

CLI, future UI, and any external service layer call `run_propose()` and format
the returned ProposeResult. This module never prints — the caller owns
presentation.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from organizer.ai.base import Classifier, ClassifierUnavailable
from organizer.ai.capabilities import Capabilities, detect_capabilities
from organizer.ai.content_extractor import SimpleContentExtractor
from organizer.ai.registry import build_classifier
from organizer.ai.training_store import TrainingStore
from organizer.config.schema import RulesConfig
from organizer.rules.engine import RuleBasedClassifier
from organizer.storage.repository import Repository

logger = logging.getLogger(__name__)

VALID_MODELS = ("rules", "ml", "llm", "api")


@dataclass
class ProposeResult:
    """Outcome of a propose run. Consumed by CLI, UI, or tests."""
    backend: str
    proposals_saved: int
    category_counts: Counter = field(default_factory=Counter)
    bootstrapped_examples: int = 0
    fell_back: bool = False
    fallback_reason: Optional[str] = None


def run_propose(
    repo: Repository,
    rules_cfg: RulesConfig,
    *,
    model: str = "ml",
    organize_root: Optional[str] = None,
    caps: Optional[Capabilities] = None,
    no_fallback: bool = False,
) -> ProposeResult:
    """Run the propose pipeline.

    Raises:
        ValueError: invalid --model value
        ClassifierUnavailable: requested model unavailable and no_fallback set
        RuntimeError: rules backend unavailable (should never happen)
    """
    if model not in VALID_MODELS:
        raise ValueError(
            f"invalid model {model!r}; valid: {', '.join(VALID_MODELS)}"
        )

    target_base = organize_root or repo.get_latest_scan_root()

    # ---- resolve requested model against available capabilities ----
    caps = caps or detect_capabilities()
    effective_model = model
    fell_back = False
    fallback_reason: Optional[str] = None

    if not getattr(caps, model, False):
        reason = caps.reasons.get(model, "unavailable on this machine")
        if no_fallback:
            raise ClassifierUnavailable(
                f"model {model!r} unavailable: {reason}",
            )
        if model == "rules":
            # rules is the ultimate fallback; if it's down, nothing works.
            raise RuntimeError(f"rules backend unavailable: {reason}")
        effective_model = "rules"
        fell_back = True
        fallback_reason = reason

    # ---- cold-start bootstrap for ML ----
    training_store: Optional[TrainingStore] = None
    bootstrapped = 0

    if effective_model == "ml":
        training_store = TrainingStore(repository=repo)
        training_store.load()
        if training_store.is_empty():
            bootstrapped = bootstrap_ml_training_store(
                repo, rules_cfg, training_store, target_base
            )

    # ---- build classifier ----
    classifier: Classifier = build_classifier(
        effective_model,
        rules_cfg,
        caps=caps,
        organize_root=target_base,
    )

    # Inject the pre-loaded training store so we don't re-embed the corpus.
    # A cleaner fix is a `training_store` kwarg on build_classifier; note for
    # Stage 7 cleanup.
    if effective_model == "ml" and training_store is not None:
        classifier.training_store = training_store  # type: ignore[attr-defined]

    # ---- run classification ----
    unproposed = repo.get_files_without_pending_proposals()
    category_counts: Counter = Counter()

    for record in unproposed:
        proposal = classifier.classify(record)
        repo.save_proposal(proposal)
        category_counts[proposal.proposed_category] += 1

    return ProposeResult(
        backend=effective_model,
        proposals_saved=len(unproposed),
        category_counts=category_counts,
        bootstrapped_examples=bootstrapped,
        fell_back=fell_back,
        fallback_reason=fallback_reason,
    )


def bootstrap_ml_training_store(
    repo: Repository,
    rules_cfg: RulesConfig,
    training_store: TrainingStore,
    target_base: Optional[str],
) -> int:
    """Seed ML training store with pseudo-labels from rules.

    Does NOT save rules proposals to the database — only populates the
    in-memory training store. The subsequent ML run produces the sole
    proposals in the DB.
    """
    unproposed = repo.get_files_without_pending_proposals()
    if not unproposed:
        return 0

    rules_clf = RuleBasedClassifier(rules_cfg, organize_root=target_base)
    extractor = SimpleContentExtractor()

    triples: list[tuple[str, str, str]] = []
    for record in unproposed:
        proposal = rules_clf.classify(record)
        text = extractor.extract_content(record.path)
        if not text:
            continue
        # Store the category folder NAME (e.g. "Academics"), not the full
        # parent path. EmbeddingClassifier composes destination paths via
        # compute_destination_path(..., category_folder, ...), so a full
        # parent like "<scan>/Academics/<date>" would double up the date.
        rule = rules_cfg.rules.get(proposal.proposed_category)
        category_folder = rule.destination if rule else proposal.proposed_category
        triples.append((text, proposal.proposed_category, category_folder))

    added = training_store.add_pseudolabels(triples)
    logger.info("Bootstrapped %d pseudo-labeled examples from rules", added)
    return added