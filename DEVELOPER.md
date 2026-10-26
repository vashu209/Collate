# Developer Guide & Architecture

This document outlines the internal architecture, design assumptions, and the
classification-tier roadmap (Tiers 0–3, described below) for the Autonomous
File Organizer project.

---

## Final Directory Tree

```
Autonomous File Organizer/
├── .gitignore                         # Git exclusion rules for virtualenvs, runtime DBs, and cache
├── pyproject.toml                     # Package metadata, dependencies, scripts, and build configuration
├── README.md                          # Project overview, quick start, CLI reference
├── DEVELOPER.md                       # This file: architecture, tiers, stages, internals
├── config/
│   └── rules.yaml                     # Default rules + optional ml: tuning block
├── organizer/                         # Core domain library (zero CLI/Typer dependencies)
│   ├── __init__.py                    # Core package export and version marker
│   ├── ai/                            # Classification tiers and scaffolding
│   │   ├── __init__.py                # AI module namespace exports
│   │   ├── base.py                    # Classifier/ContentExtractor/Embedder ABCs + ClassifierUnavailable
│   │   ├── capabilities.py            # Runtime probe of available tiers (rules/ml/llm/api)
│   │   ├── registry.py                # build_classifier() factory mapping --model names to instances
│   │   ├── classifier.py              # EmbeddingClassifier (Tier 1) + AIClassifier placeholder
│   │   ├── content_extractor.py       # SimpleContentExtractor: filename + parent + text body
│   │   ├── embedder.py                # AIEmbedder: ONNX quantized MiniLM-L6-v2
│   │   ├── training_store.py          # TrainingStore: loads feedback, batch-embeds examples
│   │   └── models/                    # MiniLM ONNX model files (fetched via scripts/, .onnx gitignored)
│   ├── config/                        # Rules configuration loading and validation
│   │   ├── __init__.py                # Config namespace exports
│   │   ├── loader.py                  # YAML loader with syntax, type, and range validation
│   │   └── schema.py                  # Dataclass schemas for rules, conditions, defaults, ml tuning
│   ├── dedup/                         # Duplicate file detection
│   │   ├── __init__.py                # Dedup namespace exports
│   │   └── hasher.py                  # Chunked SHA-256 computation and duplicate grouping
│   ├── feedback/                      # User decision audit and correction logging
│   │   ├── __init__.py                # Feedback namespace exports
│   │   └── recorder.py                # Captures user accept/reject/modify actions for future retraining
│   ├── operations/                    # Filesystem manipulation and restoration
│   │   ├── __init__.py                # Operations namespace exports
│   │   ├── executor.py                # Re-export shim for FileMover / MoveError
│   │   ├── mover.py                   # Safe cross-filesystem mover with pre-logging and verification
│   │   └── rollback.py                # Reversal engine restoring moved files with checksum verification
│   ├── propose_service.py             # Orchestration: model resolution, bootstrap, classification
│   ├── rules/                         # Deterministic classification engine (Tier 0)
│   │   ├── __init__.py                # Rules namespace exports
│   │   ├── engine.py                  # RuleBasedClassifier + compute_destination_path
│   │   ├── models.py                  # Dataclass domain models (FileRecord, Proposal, Operation, etc.)
│   │   └── proposal_engine.py         # Re-export shim for RuleBasedClassifier / compute_destination_path
│   ├── scanning/                      # Directory traversal and metadata extraction
│   │   ├── __init__.py                # Scanning namespace exports
│   │   ├── metadata.py                # Extracts sizes, timestamps, magic-byte MIME types, symlink flags
│   │   └── scanner.py                 # Directory walker yielding FileRecord objects with SHA-256 hashes
│   ├── storage/                       # SQLite database and persistence layer
│   │   ├── __init__.py                # Storage namespace exports
│   │   ├── db.py                      # Connection manager, WAL mode setup, and schema migration DDL
│   │   └── repository.py              # Thin repository CRUD for files, proposals, operations, feedback
│   └── utils/                         # Common utilities and helpers
│       ├── __init__.py                # Utils namespace exports
│       ├── logging_config.py          # Application-level logging configuration
│       └── paths.py                   # Non-destructive collision-free path generator and folder helpers
├── cli/                               # CLI presentation layer (Typer + Rich)
│   ├── __init__.py                    # CLI package marker
│   ├── main.py                        # Typer application definition and command router
│   ├── review.py                      # Top-level re-export shim for review / parse_range
│   └── commands/                      # Individual CLI command implementations
│       ├── __init__.py                # Commands package marker
│       ├── approve.py                 # Alias to review (delegates bulk-approve flags)
│       ├── duplicates.py              # Scan catalog and report exact SHA-256 duplicates
│       ├── propose.py                 # Thin wrapper around propose_service.run_propose()
│       ├── review.py                  # Paginated interactive review, bulk approve, dry-run, skip
│       ├── rollback.py                # Restore files to original paths from operation logs
│       ├── scan.py                    # Walk directories and populate SQLite catalog
│       └── status.py                  # Display summary metrics and database status tables
├── scripts/
│   ├── generate_test_data.py          # Random nested tree fixture generator
│   └── fetch_ml_model.py              # Download + verify MiniLM ONNX files
├── tests/                             # Test suite (filesystem-isolated with tmp_path)
│   ├── test_capabilities.py           # Capability probe tests
│   ├── test_cli.py                    # End-to-end CLI workflow tests using Typer CliRunner
│   ├── test_cli_model_flag.py         # --model flag wiring tests
│   ├── test_content_extractor.py      # Content extractor behavior
│   ├── test_embedder.py               # MiniLM embedder shape / normalization tests
│   ├── test_embedding_classifier.py   # kNN classifier behavior
│   ├── test_operations.py             # Move safety, collision avoidance, rollback round-trip tests
│   ├── test_propose_service.py        # Propose orchestration (no CLI)
│   ├── test_registry.py               # build_classifier factory tests
│   ├── test_rules_engine.py           # Condition matching, priority resolution, ABC conformance
│   ├── test_scanner.py                # Directory walking, metadata extraction, hash tests
│   └── test_training_store.py         # Feedback loading + pseudo-label store
└── data/                              # Default runtime SQLite database directory (gitignored)
```

---

## Classification Tiers and Development Stages

The classification engine is built as a **capability ladder**. Each rung is a
separate backend implementing the `organizer.ai.base.Classifier` ABC. The CLI
selects one at runtime; users can pick a specific tier or let the tool
auto-fall back when a tier's prerequisites are not met on their machine.

### Tiers (runtime backends)

| Tier | Name  | Backend                                 | Class                 | Hardware           | Status  |
|------|-------|-----------------------------------------|-----------------------|--------------------|---------|
| 0    | rules | Deterministic rule engine               | `RuleBasedClassifier` | Any CPU            | Shipped |
| 1    | ml    | Local sentence embeddings (MiniLM-L6)   | `EmbeddingClassifier` | Any CPU            | Shipped |
| 2    | llm   | Local small LLM (quantized, 1–4B)       | `LLMClassifier`       | dGPU recommended   | Planned |
| 3    | api   | Cloud LLM (Gemini, OpenAI, etc.)        | `APIClassifier`       | Network only       | Planned |

The `--model` flag on `organizer propose` selects a tier by name.

### Availability and fallback

`organizer.ai.capabilities.detect_capabilities()` probes each tier at runtime
and returns which are available on the current machine, plus a human-readable
reason string for any that are not. The CLI uses this to:

1. Report unavailable tiers with a reason.
2. Fall back to `rules` automatically when a requested tier cannot run,
   unless `--no-fallback` is passed.

Tier 0 is always available. This is the "zero-config" experience and the
ultimate fallback.

### Stages (historical build record)

Tiers are built in **stages**, one tier at a time. Stages exist only to make
the implementation reviewable; they never appear in user-facing strings.
Tier 1 is complete; the table below is the historical record of how it was
built.

| Stage | Scope                                                          | Status |
|-------|----------------------------------------------------------------|--------|
| 1     | Capability probe + classifier registry scaffolding             | ✅ Done |
| 2     | ONNX-backed MiniLM embedder                                    | ✅ Done |
| 3     | Content extraction (filename, path, text snippet)              | ✅ Done |
| 4     | `EmbeddingClassifier` + `TrainingStore` (kNN over feedback)    | ✅ Done |
| 5     | CLI integration + propose service layer (`--model`, bootstrap) | ✅ Done |
| 6     | Packaging (`[ml]` extra)                                       | ✅ Done |
| 7     | Confidence calibration, config knobs, docs                     | ✅ Done |

Stages 2–7 were additive: none of them modified `mover.py`, `rollback.py`, or
any CLI command other than `propose.py`. This isolation is the point of
building the `Classifier` ABC on day one.

### Where each tier plugs in

All tiers implement `organizer.ai.base.Classifier`:

```python
class Classifier(ABC):
    @abstractmethod
    def classify(self, record: FileRecord) -> Proposal:
        ...
```

Everything downstream — the `proposals` table, `FileMover`, `RollbackManager`,
`FeedbackRecorder`, and the review UI — consumes only `Proposal` objects and
is unaware of which tier produced them. Adding a new tier requires:

1. Implement `Classifier` in `organizer/ai/classifier.py`.
2. Register a lazy factory in `organizer.ai.registry._FACTORIES`.
3. Extend `detect_capabilities()` to probe the new tier's prerequisites.
4. Add a `[llm]` / `[api]` extra in `pyproject.toml` for its deps.
5. Nothing else — `--model` already accepts the tier name via
   `propose_service.VALID_MODELS`.

No changes to CLI, storage, or operations beyond that.

---

## Tier 1 tuning and design decisions

This section explains the non-obvious choices in the ML classifier, so
future-you can tune them without re-deriving the reasoning.

### Confidence formula: vote share, not similarity

`EmbeddingClassifier` returns confidence as:

```
confidence = sum(similarities of neighbors in winning class)
             / sum(similarities of all top-K neighbors)
```

Not as `top-1 similarity`. Reason:

- A **5/5 unanimous vote** is strong evidence even if the top similarity is
  only 0.7 — five independent neighbors all agree.
- A **3/2 split** with top similarity 0.9 is weak evidence — the nearest
  neighbor might be an outlier that just happens to be very close.

The vote share captures "how much of the neighborhood agrees," which
correlates better with "will the user accept this?" than raw similarity does.

The top-1 similarity is still printed in the rationale string
(`"ml: 4/5 neighbors -> academics (top cos 0.82)"`) as a secondary signal.
The user sees both: vote share as the confidence, top similarity as a
"how close is the nearest known example" hint.

### Threshold: decoupled from `defaults.min_confidence_for_proposal`

Rules confidence and ML confidence measure **different things**:

- **Rules confidence** is a static weight the human wrote into
  `rules.yaml`. `extension: pdf, confidence: 0.7` means "the author thinks a
  PDF is 70% likely to be academic." It's asserted, not measured.
- **ML confidence** is a measured statistic — the vote share of actual
  neighbor agreements.

Forcing them to share a threshold would misfit one of them. Rules confidences
cluster tightly in 0.5–0.95 (hand-authored). ML vote shares cluster around
0.6–1.0 for clean cases but can go lower on ambiguous files. A single threshold
either treats ML too leniently (causing spurious proposals) or rules too
strictly (causing fallbacks where a rule is genuinely confident).

Therefore: rules reads `defaults.min_confidence_for_proposal`; ML reads
`ml.min_confidence_for_proposal` (defaulting to 0.55 if absent). Stage 7's
config schema adds the `ml:` section so users can tune each tier
independently.

### `k = 5` neighbors

How many nearest neighbors vote. Trade-off:

- **Smaller k (3)** — more reactive to each new feedback row, noisier
  classifications. Good if the user reviews a lot and their decisions are
  consistent.
- **Larger k (10)** — more stable, slower to reflect new decisions. Good if
  the user rarely reviews and consistency matters more than responsiveness.
- **k = 5** — the standard default for text kNN. Balances both.

If `training_store` has fewer than `k` examples, all of them participate
(the vote isn't padded with empty neighbors). Once real feedback accumulates
past ~20–30 rows, `k = 5` behaves as intended.

### `pseudo_weight = 0.4`

Bootstrap examples come from the rules engine, which has known flaws. If we
weighted them equally with real feedback, the rules engine's mistakes would
dominate early ML proposals — and users would correctly perceive ML as "as
bad as rules but slower."

`pseudo_weight = 0.4` means a pseudo-labeled example counts 40% as much as a
real feedback row. Concretely: three rules-derived pseudo-labels (each
weighted 0.4) lose to two real approvals (each weighted 1.0) in the vote.

Tuning: if the rules engine is very wrong for your use case, lower to 0.2. If
it's very right, raise to 0.6 or 0.7. But **never** set it above ~0.7 —
pseudo-labels should always be strictly less influential than real feedback,
or the tier can't improve over rules.

### Bootstrap destination rule

`bootstrap_ml_training_store` in `propose_service.py` stores the **category
folder name** (e.g. `"Academics"`) in the training example, NOT the full
proposal destination path.

Reason: rules proposals' destinations are
`<base>/<category>/<date>/filename` (when the category folder exists) or
`<base>/<category>/filename` (when it doesn't). `EmbeddingClassifier.classify`
composes destinations via
`compute_destination_path(base_dir, category_folder, filename)`, which
internally applies the same date-bucketing. If the bootstrap stored the full
parent path (`<base>/<category>/<date>`), the classify step would double up
the date: `<base>/<date>/<date>/filename`.

**Invariant**: `TrainingExample.destination` always holds the *category
folder name*, never a full path. If you modify the bootstrap or add another
seeding path, respect this.

### Cold-start raise vs fallback

If `TrainingStore` is empty when `EmbeddingClassifier.classify` is called,
it raises `ClassifierUnavailable` with a hint to run bootstrap first. It does
**not** silently fall back to `_Uncategorized`.

Reason: silent fallback would produce plausible-looking-but-empty proposals.
The user would see "0 files categorized" and think ML is broken, when the
real issue is "no training data." Raising is louder but more honest; the CLI
wrapper catches it and prints the hint.

In practice, `run_propose` in `propose_service.py` auto-bootstraps on empty
store, so the raise only fires if a caller invokes `EmbeddingClassifier`
directly without going through the service.

### Model files and gitignore

`model.onnx` (~90 MB) is gitignored. `tokenizer.json` and `config.json` are
committed (small, useful to inspect). Users run `scripts/fetch_ml_model.py`
once per machine; `capabilities._ml_available()` detects the files and flips
`ml` from unavailable to available.

The fetch script prints SHA-256 hashes so they can be pinned. Once
`EXPECTED_SHA256` is populated in the script, subsequent fetches are
strict-verified — a corrupted download or upstream repo change fails loudly.

---

## The propose service layer

`organizer/propose_service.py::run_propose()` is the **only** entry point for
"propose files with a given backend." It is consumed by:

- `cli/commands/propose.py` (thin wrapper: parse args → call → format)
- Future UI / HTTP layer (would call the same function, format differently)
- Tests (direct invocation, no CLI runner needed)

This split exists because:

1. **The CLI's propose command has nontrivial logic** (model resolution,
   fallback, cold-start bootstrap) that would otherwise be trapped inside a
   Typer callback. Testable-in-isolation code belongs in the library.
2. **A future dashboard / HTTP service** will need the same logic. If it lived
   in `cli/commands/propose.py`, the UI would either call into the CLI module
   (bad coupling) or duplicate the logic (worse — drift).
3. **The core library is UI-agnostic by design.** Every other module in
   `organizer/` has no Typer/Rich/printing dependencies. `propose_service.py`
   keeps that invariant.

Everything else in `cli/commands/` is presentation-only (format tables, prompt
user). `review.py` in particular stays in `cli/` — an interactive terminal UI
is genuinely CLI-shaped and a future GUI will have its own review flow built
on `FileMover` + `FeedbackRecorder` + `Repository` directly.

---

## Common pitfalls for contributors

### Circular imports: `organizer.ai` ↔ `organizer.rules`

The two packages are mutually dependent:

- `organizer.rules.engine.RuleBasedClassifier` implements
  `organizer.ai.base.Classifier`.
- `organizer.ai.classifier.EmbeddingClassifier` uses
  `organizer.rules.engine.compute_destination_path`.

Because `organizer/rules/__init__.py` and `organizer/ai/__init__.py` eagerly
import their submodules, a top-level `from organizer.rules.engine import ...`
inside `organizer/ai/*.py` triggers a cycle:

```
ai.__init__ → ai.classifier → rules.engine → ai.base → ai.__init__ (partial) → ...
```

**Rules of thumb** for resolving and avoiding:

- **Only used in type hints** → put the import under `if TYPE_CHECKING:` at
  the top of the file. This is why `base.py` uses this pattern for
  `FileRecord` / `Proposal`.
- **Only used inside method bodies** → import inside the method. This is why
  `classifier.py` imports `compute_destination_path` inside `classify()` and
  `_fallback()` rather than at module top.
- **Used at class-definition time** (class bases, decorators, constants) →
  must be at module top; if that creates a cycle, the module structure is
  wrong and needs refactoring (e.g. moving the symbol to a neutral module).

The durable fix (post-Tier 1) would be either (a) make `rules/__init__.py`
lazy — remove eager re-exports, keep `__all__` for docs — or (b) move
`FileRecord` / `Proposal` / `RuleMatch` / `Operation` / `FeedbackRecord` from
`organizer/rules/models.py` to `organizer/core/models.py`. Neither is
urgent; the function-level import pattern works fine.

### ABC in constructor signatures, concrete class as default

Every consumer of an abstract interface should type its constructor parameter
as the ABC, and instantiate the concrete class only as the default:

```python
from organizer.ai.base import Embedder
from organizer.ai.embedder import AIEmbedder

class TrainingStore:
    def __init__(
        self,
        embedder: Optional[Embedder] = None,   # ABC in signature
    ) -> None:
        self.embedder = embedder or AIEmbedder()  # concrete as default
```

This is why `TrainingStore.__init__` and `EmbeddingClassifier.__init__` accept
`Embedder` / `ContentExtractor` (not `AIEmbedder` / `SimpleContentExtractor`).
Tests can inject fakes without inheriting from a concrete implementation.
Pylance nominal typing for `ABC` means test doubles **must** subclass the
ABC — a duck-typed class won't be accepted as assignable even if it has the
right methods.

### `Extractor` / `Embedder` / `Repository` mocks

When writing test doubles:

```python
class FakeEmbedder(Embedder):   # not: class FakeEmbedder:
    def generate_embedding(self, text: str) -> Sequence[float]:
        ...
```

If you forget the `(Embedder)` base, Pylance reports
`Argument of type "FakeEmbedder" cannot be assigned to parameter "embedder"
of type "Embedder | None"`. It's never a runtime error — the fake works fine
— but the type checker can't prove it.

---

## One-Line Responsibility Statement per File / Folder

- **`organizer/`**: Independent, framework-agnostic Python library containing all core organization logic.
- **`organizer/ai/base.py`**: Defines ABCs (`Classifier`, `ContentExtractor`, `Embedder`) and `ClassifierUnavailable`; all tiers implement these.
- **`organizer/ai/capabilities.py`**: Probes which tiers can run (module + model-file checks) with per-tier reason strings.
- **`organizer/ai/registry.py`**: Maps `--model` names to `Classifier` factories; the only place that knows tier names.
- **`organizer/ai/classifier.py`**: Implements `EmbeddingClassifier` (Tier 1, kNN over feedback embeddings) and a placeholder `AIClassifier`.
- **`organizer/ai/content_extractor.py`**: `SimpleContentExtractor` — filename + parent dir + up-to-2-KB body; PDFs via pypdf, optional.
- **`organizer/ai/embedder.py`**: `AIEmbedder` — ONNX quantized MiniLM-L6-v2, mean-pooled + L2-normalized, batched `encode_batch()`.
- **`organizer/ai/training_store.py`**: Loads approved/modified feedback rows, embeds snippets, exposes pseudo-label injection and rejection tracking.
- **`organizer/ai/models/`**: MiniLM ONNX + tokenizer files (`.onnx` gitignored; fetched via `scripts/fetch_ml_model.py`).
- **`organizer/config/schema.py`**: Type-safe dataclass definitions and constraint validation for rules, defaults, and ml tuning configuration.
- **`organizer/config/loader.py`**: Parses, validates, and instantiates configuration objects from YAML files.
- **`organizer/dedup/hasher.py`**: Computes streaming SHA-256 hashes and clusters files into duplicate groups.
- **`organizer/feedback/recorder.py`**: Persists user approval, rejection, and destination edits (training data for Tier 1).
- **`organizer/operations/mover.py`**: Atomically moves files with pre-operation DB logging, collision avoidance, and post-copy hash checks.
- **`organizer/operations/rollback.py`**: Safely reverses completed moves back to original locations after verifying file integrity.
- **`organizer/operations/executor.py`**: Convenience re-export of `FileMover` / `MoveError`.
- **`organizer/propose_service.py`**: Orchestration layer — resolves `--model`, bootstraps ML on cold start, invokes classifier, returns typed `ProposeResult`; no printing, no CLI deps.
- **`organizer/rules/models.py`**: Houses core dataclasses (`FileRecord`, `Condition`, `Rule`, `RuleMatch`, `Proposal`, `Operation`, `FeedbackRecord`).
- **`organizer/rules/engine.py`**: Implements `RuleBasedClassifier` (Tier 0) + `compute_destination_path` behind the `Classifier` ABC.
- **`organizer/rules/proposal_engine.py`**: Re-export shim for `RuleBasedClassifier` and `compute_destination_path`.
- **`organizer/scanning/metadata.py`**: Probes file attributes including POSIX/Windows timestamps and magic-byte MIME types.
- **`organizer/scanning/scanner.py`**: Recursively scans directory trees and yields complete `FileRecord` structures.
- **`organizer/storage/db.py`**: Manages SQLite connections, enables WAL mode and foreign keys, provisions schemas.
- **`organizer/storage/repository.py`**: Provides transactional CRUD queries across files, proposals, operations, and feedback.
- **`organizer/utils/paths.py`**: Generates unique non-colliding file paths (`name_1.ext`) and ensures directory hierarchy.
- **`organizer/utils/logging_config.py`**: Configures runtime logging formatters and stream handlers.
- **`cli/`**: Presentation and interactive terminal interface layer built with Typer and Rich.
- **`cli/main.py`**: Command router and CLI entrypoint exposing all subcommands.
- **`cli/review.py`**: Top-level re-export of `review` / `parse_range` from `commands/`.
- **`cli/commands/scan.py`**: CLI handler for cataloging files and computing checksums.
- **`cli/commands/propose.py`**: Thin CLI wrapper over `propose_service.run_propose()`.
- **`cli/commands/approve.py`**: CLI alias delegating to `review` for bulk-approve workflows.
- **`cli/commands/review.py`**: Paginated interactive review, bulk approve by category/range, dry-run, skip.
- **`cli/commands/rollback.py`**: CLI handler for reversing move operations using transaction logs.
- **`cli/commands/duplicates.py`**: CLI handler for discovering and displaying exact duplicates.
- **`cli/commands/status.py`**: CLI handler for rendering system-wide health and metric tables.
- **`config/rules.yaml`**: Declarative rule specification + optional `ml:` tuning block (k, pseudo_weight, threshold).
- **`scripts/generate_test_data.py`**: Fixture generator producing nested dirs + categorized files for testing.
- **`scripts/fetch_ml_model.py`**: Downloads and SHA-256-verifies MiniLM ONNX files for Tier 1.
- **`tests/`**: Pytest suite: unit (capabilities, registry, embedder, extractor, classifier, training store, rules), operations, propose service, and CLI flows.
- **`pyproject.toml`**: Packaging configuration declaring console scripts, dependencies, and `[dev]`/`[ml]` extras.

---

## The `rules.yaml` Format Explained

The rules file is written in YAML and defines how files should be categorized
based on deterministic criteria. This is the Tier 0 (rules) backend's
configuration; Tier 1 uses the same file to seed its bootstrap pseudo-labels,
and an optional `ml:` block tunes the ML tier.

```yaml
version: 1
organize_root: "~/Organized"

rules:
  academics:
    priority: 10
    destination: Academics
    match_any:
      - type: extension
        values: [pdf, docx, pptx]
        confidence: 0.7
      - type: keyword_in_name
        values: [lecture, assignment, syllabus, notes, homework]
        confidence: 0.8
      - type: path_contains
        values: [Semester, Coursework, Lectures]
        confidence: 0.75

  images:
    priority: 20
    destination: Images
    match_any:
      - type: extension
        values: [jpg, jpeg, png, heic, gif, webp, raw]
        confidence: 0.95

defaults:
  unmatched_category: uncategorized
  unmatched_destination: _Uncategorized
  min_confidence_for_proposal: 0.5

ml:
  k: 5
  pseudo_weight: 0.4
  min_confidence_for_proposal: 0.55
```

### Top-Level Fields

- **`version`** (`int`): Configuration schema version (currently `1`).
- **`organize_root`** (`str`): Base destination directory. Supports `~`.
- **`rules`** (`mapping`): Map of category names to rule definitions.
- **`defaults`** (`mapping`): Fallback behaviors for the rules tier.
- **`ml`** (`mapping`, optional): Tier 1 tuning knobs. If absent, ML uses
  hardcoded defaults (`k=5`, `pseudo_weight=0.4`, `min_confidence=0.55`).

### Rule Specification

- **`priority`** (`int`): Integer weight determining precedence. Highest wins.
- **`destination`** (`str`): Subfolder relative to `organize_root`.
- **`match_any`** (`list`): List of match conditions. Any match triggers the rule.

### Condition Types

All string matching is **case-insensitive**:
1. **`extension`**: Matches file extension without leading dot.
2. **`keyword_in_name`**: Substring match against the file's base name.
3. **`path_contains`**: Substring match against the full path.
4. **`confidence`** (`float` 0.0–1.0): Static weight for this condition.

### Resolution & Conflict Strategy

1. **Intra-Rule**: Highest-confidence condition represents the rule.
2. **Inter-Rule**: Highest `priority` wins; on a tie, highest `confidence`.
3. **Threshold**: If winning confidence `< defaults.min_confidence_for_proposal`,
   the file goes to `defaults.unmatched_category` and `unmatched_destination`.

### Destination Resolution

`compute_destination_path` in `organizer/rules/engine.py` applies date-bucketing:
if `<organize_root>/<Category>/` exists, use `<Category>/<YYYY-MM-DD>/`;
otherwise just `<Category>/`. Tier 1 reuses this helper so ML proposals land in
the same layout as rules.

### ML Tuning Block

- **`k`** (`int`): Number of nearest neighbors in the vote. Larger is more
  stable but slower to reflect new feedback; smaller is more reactive but
  noisier. Default `5`.
- **`pseudo_weight`** (`float` 0.0–1.0): How much a rules-derived bootstrap
  example counts relative to a real user feedback row. Default `0.4` — pseudo
  counts 40% as much. **Never exceed ~0.7** or ML can't improve over rules.
- **`min_confidence_for_proposal`** (`float` 0.0–1.0): Vote-share threshold
  below which the ML tier falls back to `_Uncategorized`. Default `0.55`.
  Decoupled from `defaults.min_confidence_for_proposal`; see "Tier 1 tuning
  and design decisions" above.

---

## Full CLI Command Reference

Install editable:
```bash
pip install -e .
```
This registers the `organizer` console script.

```
Usage: organizer [OPTIONS] COMMAND [ARGS]...
```

### 1. `organizer scan`

Walks a target directory, extracts metadata, calculates SHA-256 checksums,
and updates the SQLite catalog.

```bash
organizer scan <path> [--recursive / --no-recursive] [--db PATH]
```

- `<path>`: Directory to scan (required).
- `--recursive / --no-recursive`: Recursive traversal (default: `--no-recursive`).
- `--db <str>`: SQLite path (default: `data/organizer.db`).

### 2. `organizer propose`

Runs the selected backend over scanned files without pending proposals.

```bash
organizer propose [--model {rules|ml|llm|api}]
                  [--config PATH] [--min-confidence FLOAT]
                  [--organize-root PATH] [--no-fallback] [--db PATH]
```

- `--model`: Backend tier. Default `ml`; falls back to `rules` if the tier is
  unavailable unless `--no-fallback` is set.
- `--config <str>`: Rules YAML path (default: `config/rules.yaml`).
- `--min-confidence <float>`: Overrides `defaults.min_confidence_for_proposal`
  for the rules tier (ML tier reads `ml.min_confidence_for_proposal` from the
  config).
- `--organize-root <str>`: Base directory for organized folders (defaults to
  the latest scan root).
- `--no-fallback`: Fail hard instead of falling back to `rules`.
- `--db <str>`: SQLite path.

The propose pipeline lives in `organizer/propose_service.py`; the CLI is a
thin wrapper around it. A future UI or HTTP service calls the same function.

### 3. `organizer approve`

Alias delegating to `review`. Accepts the same flags.

### 4. `organizer review`

Interactive paginated review. Same flags as `approve`, plus inline commands
`y <id|range>`, `n <id|range>`, `e <id>`, `v <id>`, `s <id>`, `sa`, `sc`,
`sr <range>`, `b`, `n`, `ps <size>`, `q`. See `cli/commands/review.py`.

### 5. `organizer rollback`

Reverses completed moves. Same safety checks: destination checksum verified
against the original operation; corrupted files are refused.

```bash
organizer rollback [--last N | --operation-id ID | --all] [--db PATH]
```

### 6. `organizer duplicates`

Read-only duplicate report via SHA-256. Same flags as before.

### 7. `organizer status`

Status summary table.

---

## Assumptions Made

1. **Storage Location**: Default DB at `data/organizer.db`; parent auto-created.
2. **Path Normalization**: All paths expanded and resolved to absolute before storage.
3. **Collision Strategy**: Numeric suffix (`_1`, `_2`) on destination collisions.
4. **Symlink Safety**: Symlinks skipped by default.
5. **Cross-Device Move Reliability**: `shutil.copy2` → destination SHA-256 verify → source delete.
6. **Pre-Operation Journaling**: Operation logged `pending` before FS mutation.
7. **Model Files Not Committed**: `*.onnx` gitignored; `tokenizer.json` and `config.json` committed.

---

## Adding a New Classification Tier

See "Where each tier plugs in" above. Concretely, for Tier 2 (`LLMClassifier`):

1. Implement `Classifier` in `organizer/ai/classifier.py`.
2. Register `_build_llm` in `organizer/ai/registry.py`.
3. Implement `_llm_available()` in `organizer/ai/capabilities.py` (probe
   `llama_cpp`, GPU, model files).
4. Add `[llm]` extra in `pyproject.toml`.
5. Nothing else — `propose --model llm` already accepts the name; the service
   resolves availability and falls back or raises.

Everything downstream (repository, mover, rollback, feedback, review UI) is
tier-agnostic.

### Where Tier 1 uses human feedback

The `feedback` table is Tier 1's training corpus. `TrainingStore` loads every
`approved` / `modified` row, re-extracts the source file's snippet, embeds it,
and caches the vector. `EmbeddingClassifier` votes across the top-K nearest
neighbors, weighting real feedback at 1.0 and bootstrap pseudo-labels at
`pseudo_weight` (0.4). Rejected categories receive a 0.5× vote penalty. This
is why every `[y]` / `[n]` / `[e]` in `organizer review` silently improves
future ML accuracy — the feedback table is the training set, no separate
training step required.

---

## Test Data

Fixtures via `scripts/generate_test_data.py` (stdlib only).

### Basic — 120 files in `./testdata`
```bash
python scripts/generate_test_data.py
```

### Deterministic (same layout every run)
```bash
python scripts/generate_test_data.py --seed 42
```

### Bigger fixture with duplicate groups
```bash
python scripts/generate_test_data.py -n 500 --max-depth 6 --dupes 5 -o /tmp/bigfixture --clean
```

### Drive the organizer against it
```bash
organizer scan testdata
organizer propose --model rules      # explicit tier; --model ml also works
organizer duplicates
organizer approve --dry-run
```