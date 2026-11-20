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
import numpy as np
from typing import Optional

from organizer.ai.base import Classifier, ClassifierUnavailable
from organizer.ai.capabilities import Capabilities, detect_capabilities
from organizer.ai.content_extractor import SimpleContentExtractor
from organizer.ai.registry import build_classifier
from organizer.ai.training_store import TrainingStore
from organizer.ai.training_store import TrainingExample
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
    """Run the propose pipeline."""

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
    # NOTE: training_store is passed via kwargs, so registry.py handles it correctly.
    classifier: Classifier = build_classifier(
        effective_model,
        rules_cfg,
        caps=caps,
        organize_root=target_base,
        training_store=training_store if effective_model == "ml" else None,
    )

    # ---- run classification ----
    unproposed = repo.get_files_without_pending_proposals(root_path=target_base)
    category_counts: Counter = Counter()
    proposals_saved = 0

    try:
        # We assume repo has a context manager for transactions. If not, 
        # you can remove the `with repo._get_conn() as conn:` line.
        for record in unproposed:
            proposal = classifier.classify(record)
            repo.save_proposal(proposal)
            category_counts[proposal.proposed_category] += 1
            proposals_saved += 1
            
    except ClassifierUnavailable as e:
        # ML store is empty (bootstrap failed to find confident matches)
        logger.warning("ML classification failed, falling back to rules: %s", e)
        effective_model = "rules"
        fell_back = True
        fallback_reason = f"ML failed ({e}), fell back to rules"
        
        # Fallback to rules for all files
        rules_clf = RuleBasedClassifier(rules_cfg, organize_root=target_base)
        category_counts.clear()
        proposals_saved = 0
        
        for record in unproposed:
            proposal = rules_clf.classify(record)
            repo.save_proposal(proposal)
            category_counts[proposal.proposed_category] += 1
            proposals_saved += 1

    return ProposeResult(
        backend=effective_model,
        proposals_saved=proposals_saved,
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
    # Restrict to current scan root
    unproposed = repo.get_files_without_pending_proposals(root_path=target_base)
    if not unproposed:
        return 0

    rules_clf = RuleBasedClassifier(rules_cfg, organize_root=target_base)
    extractor = SimpleContentExtractor()

    # 1. Extract snippets in a single pass
    records_with_text = []
    for record in unproposed:
        proposal = rules_clf.classify(record)
        
        # Only learn from confident rules matches
        if (
            proposal.confidence < 0.70 
            or proposal.proposed_category == rules_cfg.defaults.unmatched_category
        ):
            continue

        text = extractor.extract_content(record.path)
        if not text:
            continue
            
        rule = rules_cfg.rules.get(proposal.proposed_category)
        category_folder = rule.destination if rule else proposal.proposed_category
        records_with_text.append((record.id, text, proposal.proposed_category, category_folder))

    # 2. Batch embed all snippets at once (NEW: Performance fix)
    if not records_with_text:
        return 0
        
    texts = [t for (_id, t, _cat, _dest) in records_with_text]
    vectors = training_store.embedder.encode_batch(texts)

    # 3. Add to store with pre-computed vectors (NEW: Bypasses the per-file loop)
    added = 0
    for (file_id, text, category, dest), vec in zip(records_with_text, vectors):
        training_store.examples.append(
            TrainingExample(
                text=text,
                category=category,
                destination=dest,
                source="pseudolabel",
                file_id=file_id,
                vector=np.asarray(vec, dtype=np.float32),
            )
        )
        added += 1

    logger.info("Bootstrapped %d confident pseudo-labeled examples from rules", added)
    return added