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
│   └── rules.yaml                     # Default classification rules, categories, priorities, and fallbacks
├── organizer/                         # Core domain library (zero CLI/Typer dependencies)
│   ├── __init__.py                    # Core package export and version marker
│   ├── ai/                            # Classification tiers and scaffolding
│   │   ├── __init__.py                # AI module namespace exports
│   │   ├── base.py                    # Classifier/ContentExtractor/Embedder ABCs + ClassifierUnavailable
│   │   ├── capabilities.py            # Runtime probe of available tiers (rules/ml/llm/api)
│   │   ├── registry.py                # build_classifier() factory mapping --model names to instances
│   │   ├── classifier.py              # EmbeddingClassifier stub (Stage 4 replaces) + AIClassifier stub
│   │   ├── content_extractor.py       # Placeholder content extractor stub (Stage 3)
│   │   ├── embedder.py                # AIEmbedder ONNX MiniLM (Stage 2)
│   │   ├── training_store.py          # TrainingStore stub (Stage 4)
│   │   └── models/                    # MiniLM ONNX model files (Stage 2; fetched via scripts/)
│   ├── config/                        # Rules configuration loading and validation
│   │   ├── __init__.py                # Config namespace exports
│   │   ├── loader.py                  # YAML loader with syntax, type, and range validation
│   │   └── schema.py                  # Dataclass schemas for rules, conditions, and default options
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
│       ├── propose.py                 # Evaluate unproposed files against the selected classifier
│       ├── review.py                  # Paginated interactive review, bulk approve, dry-run, skip
│       ├── rollback.py                # Restore files to original paths from operation logs
│       ├── scan.py                    # Walk directories and populate SQLite catalog
│       └── status.py                  # Display summary metrics and database status tables
├── scripts/
│   ├── generate_test_data.py          # Random nested tree fixture generator
│   └── fetch_ml_model.py              # Download + verify MiniLM ONNX files (Stage 2)
├── tests/                             # Test suite (filesystem-isolated with tmp_path)
│   ├── test_capabilities.py           # Capability probe tests (Stage 1)
│   ├── test_cli.py                    # End-to-end CLI workflow tests using Typer CliRunner
│   ├── test_embedder.py               # MiniLM embedder shape / normalization tests (Stage 2)
│   ├── test_operations.py             # Move safety, collision avoidance, rollback round-trip tests
│   ├── test_registry.py               # build_classifier factory tests (Stage 1)
│   ├── test_rules_engine.py           # Condition matching, priority resolution, ABC conformance
│   └── test_scanner.py                # Directory walking, metadata extraction, and hash tests
└── data/                              # Default runtime SQLite database directory (gitignored)
```

---

## Classification Tiers and Development Stages

The classification engine is built as a **capability ladder**. Each rung is a
separate backend implementing the `organizer.ai.base.Classifier` ABC. The CLI
selects one at runtime; users can pick a specific tier or let the tool
auto-fall back when a tier's prerequisites are not met on their machine.

### Tiers (runtime backends)

| Tier | Name  | Backend                                 | Class                 | Hardware           | Status      |
|------|-------|-----------------------------------------|-----------------------|--------------------|-------------|
| 0    | rules | Deterministic rule engine               | `RuleBasedClassifier` | Any CPU            | Shipped     |
| 1    | ml    | Local sentence embeddings (MiniLM-L6)   | `EmbeddingClassifier` | Any CPU            | In progress |
| 2    | llm   | Local small LLM (quantized, 1–4B)       | `LLMClassifier`       | dGPU recommended   | Planned     |
| 3    | api   | Cloud LLM (Gemini, OpenAI, etc.)        | `APIClassifier`       | Network only       | Planned     |

The `--model` flag on `organizer propose` selects a tier by name.

### Availability and fallback

`organizer.ai.capabilities.detect_capabilities()` probes each tier at runtime
and returns which are available on the current machine, plus a human-readable
reason string for any that are not. The CLI uses this to:

1. Gray out unavailable tiers in `--help` / status output.
2. Fall back to `rules` automatically when a requested tier cannot run,
   unless `--no-fallback` is passed.

Tier 0 is always available. This is the "zero-config" experience and the
ultimate fallback.

### Stages (internal development milestones)

Tiers are built in **stages**, one tier at a time. Stages exist only to make
the implementation reviewable; they never appear in user-facing strings.

The current development effort is **Tier 1**, broken into seven stages:

| Stage | Scope                                                          | Files added / modified                                                                                             |
|-------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| 1     | Capability probe + classifier registry scaffolding             | `organizer/ai/base.py`, `capabilities.py`, `registry.py`, `classifier.py` (stub), `training_store.py` (stub)       |
| 2     | ONNX-backed MiniLM embedder                                    | `organizer/ai/embedder.py`, `scripts/fetch_ml_model.py`, `organizer/ai/models/minilm-l6-v2/`                       |
| 3     | Content extraction (filename, path, text snippet)              | `organizer/ai/content_extractor.py`                                                                                |
| 4     | `EmbeddingClassifier` + `TrainingStore` (kNN over feedback)    | `organizer/ai/classifier.py`, `training_store.py`                                                                  |
| 5     | CLI integration (`--model` flag, auto-bootstrap, fallback UX)  | `cli/commands/propose.py`                                                                                          |
| 6     | Packaging (`[ml]` extra, model data)                           | `pyproject.toml`                                                                                                   |
| 7     | Confidence calibration, config knobs, docs                     | `organizer/config/schema.py`, `config/rules.yaml`, docs                                                            |

Once Tier 1 ships, `--model ml` becomes the default on machines that can run
it; `--model rules` remains the always-available fallback.

Stages 2–7 are additive: none of them modify `mover.py`, `rollback.py`,
`repository.py`, or any CLI command other than `propose.py`. This isolation is
the point of building the `Classifier` ABC on day one.

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
4. Add a `[ml]` / `[llm]` / `[api]` extra in `pyproject.toml` for its deps.
5. (Stage 5 equivalent) Wire the tier into `cli/commands/propose.py`'s
   `--model` flag validation and fallback logic — usually zero code if the
   tier name is already in `detect_capabilities()`.

No changes to CLI, storage, or operations beyond that.

### Tier 1 internals (in progress)

Tier 1 works as follows:

1. **Content extraction** (`content_extractor.py`, Stage 3) — reads a short
   text snippet from the file: filename + parent directory + up to 512 chars
   of decoded text (for text-like files), or filename + parent only for
   binaries.
2. **Embedding** (`embedder.py`, Stage 2) — MiniLM-L6-v2 (ONNX, quantized)
   converts the snippet to a 384-dim L2-normalized vector.
3. **Nearest-neighbor classification** (`classifier.py`, Stage 4) — compares
   the vector against a training store of previously-labeled examples
   (drawn from the `feedback` table) and picks the winning category by
   weighted majority of the top-K neighbors.
4. **Bootstrap** (Stage 5) — on first run with no feedback yet, the rules
   engine's proposals are recorded as low-weight pseudo-labels so ML has
   something to work with from day one.

Confidence for Tier 1 is `sum(similarities of winning class) /
sum(similarities of all top-K)` — a *relative* score, not a probability.
`min_confidence_for_proposal` in `rules.yaml` therefore means different
things across tiers; Tier 1 users are advised to start around `0.55` and
tune. See Stage 7.

### Model acquisition

Tier 1 depends on three files: `model.onnx` (quantized MiniLM-L6-v2),
`tokenizer.json`, and `config.json`, installed under
`organizer/ai/models/minilm-l6-v2/`. These are not committed to git; run:

```bash
python scripts/fetch_ml_model.py
```

once per machine. The script downloads from HuggingFace (`Xenova/all-MiniLM-L6-v2`),
prints SHA-256 hashes, and can be re-run idempotently. `capabilities.py`
detects the files and flips `ml` from unavailable to available.

---

## One-Line Responsibility Statement per File / Folder

- **`organizer/`**: Independent, framework-agnostic Python library containing all core organization logic.
- **`organizer/ai/base.py`**: Defines ABCs (`Classifier`, `ContentExtractor`, `Embedder`) and `ClassifierUnavailable`; all tiers implement these.
- **`organizer/ai/capabilities.py`**: Probes which tiers can run (module + model-file checks) with per-tier reason strings.
- **`organizer/ai/registry.py`**: Maps `--model` names to `Classifier` factories; the only place that knows tier names.
- **`organizer/ai/classifier.py`**: Concrete classifier implementations (`EmbeddingClassifier` currently a Stage-4 stub).
- **`organizer/ai/content_extractor.py`**: Extracts a text snippet from a file (Stage-3 stub).
- **`organizer/ai/embedder.py`**: ONNX-backed MiniLM embedder implementing the `Embedder` ABC.
- **`organizer/ai/training_store.py`**: Loads labeled examples from the feedback table for kNN (Stage-4 stub).
- **`organizer/ai/models/`**: MiniLM ONNX + tokenizer files, populated by `scripts/fetch_ml_model.py`.
- **`organizer/config/schema.py`**: Type-safe dataclass definitions and constraint validation for rules configuration.
- **`organizer/config/loader.py`**: Parses, validates, and instantiates configuration objects from YAML files.
- **`organizer/dedup/hasher.py`**: Computes streaming SHA-256 hashes and clusters files into duplicate groups.
- **`organizer/feedback/recorder.py`**: Persists user approval, rejection, and destination edits (training data for Tier 1).
- **`organizer/operations/mover.py`**: Atomically moves files with pre-operation DB logging, collision avoidance, and post-copy hash checks.
- **`organizer/operations/rollback.py`**: Safely reverses completed moves back to original locations after verifying file integrity.
- **`organizer/operations/executor.py`**: Convenience re-export of `FileMover` / `MoveError`.
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
- **`cli/commands/propose.py`**: CLI handler for generating organization proposals via the selected classifier.
- **`cli/commands/approve.py`**: CLI alias delegating to `review` for bulk-approve workflows.
- **`cli/commands/review.py`**: Paginated interactive review, bulk approve by category/range, dry-run, skip.
- **`cli/commands/rollback.py`**: CLI handler for reversing move operations using transaction logs.
- **`cli/commands/duplicates.py`**: CLI handler for discovering and displaying exact duplicates.
- **`cli/commands/status.py`**: CLI handler for rendering system-wide health and metric tables.
- **`config/rules.yaml`**: Declarative rule specification containing match conditions, destination mappings, and priority weights.
- **`scripts/generate_test_data.py`**: Fixture generator producing nested dirs + categorized files for testing.
- **`scripts/fetch_ml_model.py`**: Downloads and SHA-256-verifies MiniLM ONNX files for Tier 1.
- **`tests/`**: Pytest suite: unit (capabilities, registry, embedder, rules), operations, and CLI flows.
- **`pyproject.toml`**: Packaging configuration declaring console scripts and dependencies.

---

## The `rules.yaml` Format Explained

The rules file is written in YAML and defines how files should be categorized based on deterministic criteria. This is the Tier 0 (rules) backend's configuration; Tier 1 uses the same file to seed its bootstrap pseudo-labels.

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
```

### Top-Level Fields

- **`version`** (`int`): Configuration schema version (currently `1`).
- **`organize_root`** (`str`): Base destination directory where categorized subfolders are created. Supports `~` home directory expansion.
- **`rules`** (`mapping`): Map of category names to rule definitions.
- **`defaults`** (`mapping`): Fallback behaviors when no rule matches or confidence is below threshold.

### Rule Specification

Each rule under `rules` contains:
- **`priority`** (`int`): Integer weight determining precedence. When multiple rules match a file, the category with the **highest priority wins**.
- **`destination`** (`str`): Subfolder relative to `organize_root` where matching files will be moved.
- **`match_any`** (`list`): List of match conditions. If **any** condition matches, the rule is considered triggered.

### Condition Types

All string matching is **case-insensitive**. Supported condition types:
1. **`extension`**: Matches against the file extension (without leading dot). E.g. `[pdf, docx]`.
2. **`keyword_in_name`**: Checks whether any of the listed substrings appear inside the file's base name. E.g. `[lecture, syllabus]`.
3. **`path_contains`**: Checks whether any of the listed substrings appear anywhere in the file's full path. E.g. `[Semester, Coursework]`.
4. **`confidence`** (`float` between 0.0 and 1.0): Static, human-assigned weight associated with the condition.

### Resolution & Conflict Strategy

1. **Intra-Rule Matching**: If a file matches multiple conditions within the same rule, the condition with the **highest confidence** represents the rule.
2. **Inter-Rule Matching**: If a file matches multiple different rules:
   - The rule with the highest `priority` is selected.
   - If two matching rules share the same priority, the rule with the highest `confidence` breaks the tie.
3. **Threshold Check**: If the winning match has `confidence < min_confidence_for_proposal`, the file is assigned to `defaults.unmatched_category` and directed to `defaults.unmatched_destination`.

### Destination Resolution

`compute_destination_path` in `organizer/rules/engine.py` implements
date-bucketing: if `<organize_root>/<Category>/` already exists on disk, the
file lands in `<organize_root>/<Category>/<YYYY-MM-DD>/`; otherwise it goes
directly into `<organize_root>/<Category>/`. Tier 1 reuses this helper so ML
proposals land in the same directory layout as rules.

---

## Full CLI Command Reference

Install the project in editable mode within a virtual environment:
```bash
pip install -e .
```
This registers the global console script `organizer`.

```
Usage: organizer [OPTIONS] COMMAND [ARGS]...
```

### 1. `organizer scan`

Walks a target directory, extracts filesystem metadata (size, timestamps, extension, magic-byte MIME type), calculates SHA-256 checksums, and updates the SQLite catalog.

```bash
organizer scan <path> [--recursive / --no-recursive] [--db PATH]
```

- `<path>`: Directory to scan (required).
- `--recursive / --no-recursive`: Enable/disable recursive subfolder traversal (default: `--no-recursive`).
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Example:*
```bash
organizer scan ~/Downloads --recursive
```

### 2. `organizer propose`

Runs the selected classification backend over all scanned files in the database that do not currently have a pending proposal. Creates pending `Proposal` records.

```bash
organizer propose [--config PATH] [--min-confidence FLOAT]
                  [--organize-root PATH] [--db PATH]
```

- `--config <str>`: Path to rules YAML file (default: `config/rules.yaml`).
- `--min-confidence <float>`: Override minimum confidence threshold required for proposals.
- `--organize-root <str>`: Base directory for organized folders (defaults to latest scan root).
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*(Stage 5 will add `--model rules|ml|llm|api` and `--no-fallback`.)*

*Example:*
```bash
organizer propose --config config/rules.yaml --min-confidence 0.6
```

### 3. `organizer approve`

Convenience alias delegating to `organizer review`. Accepts the same flags.

```bash
organizer approve [--all] [--approve-category CATEGORY] [--approve-range RANGE]
                  [--filter-category CATEGORY] [--page-size N] [--dry-run] [--db PATH]
```

- `--all`: Approve and execute all pending proposals immediately without prompting.
- `--approve-category <str>`: Bulk approve proposals matching a specific category.
- `--approve-range <str>`: Bulk approve a display-ID range (e.g., `1-15`, `1,4,7`).
- `--filter-category <str>`: Restrict the review session to one category.
- `--page-size <int>`: Rows per page in dry-run and interactive view (default 20).
- `--dry-run`: Previews pending moves without touching files or the database.
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

### 4. `organizer review`

Interactive paginated review. Same flags as `approve`, plus inline commands for
approve/reject/edit/skip/view/back/next. See `cli/commands/review.py` for the
full command grammar (`y <id|range>`, `n <id|range>`, `e <id>`, `v <id>`,
`s <id>`, `sa`, `sc`, `sr <range>`, `b`, `n`, `ps <size>`, `q`).

### 5. `organizer rollback`

Safely reverses completed move operations, returning files to their exact original source paths.

```bash
organizer rollback [--last N | --operation-id ID | --all] [--db PATH]
```

- `--last <int>`, `-n <int>`: Roll back the most recent N completed operations.
- `--operation-id <int>`, `-id <int>`: Roll back a specific operation by its database ID.
- `--all`: Roll back all completed operations recorded in the database.
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Safety Checks During Rollback:*
- Validates that the file still exists at its destination.
- Verifies that the destination file's SHA-256 matches the original operation checksum. If the file was edited or corrupted, rollback is aborted to prevent data loss.
- Checks that the source path is not blocked by a different file.
- Marks the operation as `rolled_back` in the database.

*Example:*
```bash
organizer rollback --last 5
organizer rollback --all
```

### 6. `organizer duplicates`

Scans the catalog and prints groups of exact duplicate files identified by matching SHA-256 hashes. Read-only.

```bash
organizer duplicates [<path>] [--db PATH]
```

- `[path]`: Optional directory prefix filter.
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Example:*
```bash
organizer duplicates ~/Downloads
```

### 7. `organizer status`

Renders an overview table detailing files scanned, proposals pending/approved/rejected/executed, operations completed/rolled back/failed, and total feedback log count.

```bash
organizer status [--db PATH]
```

---

## Assumptions Made

1. **Storage Location**: The default database path is `data/organizer.db`. The parent directory is created automatically upon first run.
2. **Path Normalization**: All file paths are expanded and resolved to absolute paths before storage and operation execution.
3. **Collision Strategy**: When a move destination already exists on disk, a numeric suffix (`_1`, `_2`) is appended before the file extension. This ensures non-destructive execution under all circumstances.
4. **Symlink Safety**: Symlinks are identified during metadata extraction and skipped by default to avoid accidental traversal cycles or cross-link moves.
5. **Cross-Device Move Reliability**: Instead of relying on atomic `os.rename` (which fails across filesystem and mount boundaries), moves are executed via `shutil.copy2` → destination SHA-256 verification → source deletion.
6. **Pre-Operation Journaling**: The operation is recorded with status `pending` in SQLite *before* filesystem modification. If the process is halted mid-move, the incomplete operation can be audited and resolved.
7. **Model Files Are Not Committed**: MiniLM ONNX files (~90 MB) are fetched by `scripts/fetch_ml_model.py`. `organizer/ai/models/` is expected to be gitignored for the `.onnx` file specifically.

---

## Adding a New Classification Tier

The architecture was intentionally designed so a new tier requires **zero
changes** to the CLI, database repository, or filesystem operations.

### The Seam Architecture

The contract between classification and everything downstream is two constructs:

1. **`organizer.rules.models.Proposal`** — the universal data contract:

```python
@dataclass
class Proposal:
    source_path: str
    proposed_category: str
    proposed_destination: str
    confidence: float
    rationale: str
    id: Optional[int] = None
    file_id: Optional[int] = None
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
```

2. **`organizer.ai.base.Classifier`** — the ABC every tier implements:

```python
class Classifier(ABC):
    @abstractmethod
    def classify(self, record: FileRecord) -> Proposal:
        ...
```

`RuleBasedClassifier` (Tier 0) already implements this interface. Tier 1
(`EmbeddingClassifier`) does the same.

### Adding Tier 2 or Tier 3

The mechanics are identical for either:

1. **Implement the class** in `organizer/ai/classifier.py`:

```python
from organizer.ai.base import Classifier
from organizer.rules.models import FileRecord, Proposal

class LLMClassifier(Classifier):
    def __init__(self, rules_cfg, *, organize_root=None, today_str=None):
        ...

    def classify(self, record: FileRecord) -> Proposal:
        # extract content -> prompt local LLM -> parse structured response
        return Proposal(
            file_id=record.id,
            source_path=record.path,
            proposed_category=prediction.category,
            proposed_destination=str(...),
            confidence=prediction.confidence,
            rationale=prediction.explanation,
        )
```

2. **Register a lazy factory** in `organizer/ai/registry.py`:

```python
def _build_llm(rules_cfg, *, organize_root=None, today_str=None, **_):
    from organizer.ai.classifier import LLMClassifier
    return LLMClassifier(rules_cfg, organize_root=organize_root, today_str=today_str)

_FACTORIES["llm"] = _build_llm
```

3. **Probe prerequisites** in `organizer/ai/capabilities.py`:

```python
def _llm_available() -> tuple[bool, str]:
    if not _module_available("llama_cpp"):
        return False, "missing llama-cpp-python; install with 'pip install file-organizer[llm]'"
    if not _gpu_available():
        return False, "local LLM requires a GPU (see docs)"
    return True, ""
```

4. **Add the optional dependency group** in `pyproject.toml`:

```toml
[project.optional-dependencies]
llm = ["llama-cpp-python>=0.2"]
```

5. **Nothing else.** `repository.save_proposal`, `FileMover`, `RollbackManager`,
   `FeedbackRecorder`, and `cli/commands/review.py` all consume `Proposal`
   objects identically regardless of which tier produced them. The review UI
   has no concept of "rules vs ML vs LLM" — it just shows a proposal with a
   confidence and a rationale string.

### What does NOT need to change

- `organizer.storage.repository.Repository`: accepts and saves `Proposal` objects identically.
- `organizer.operations.mover.FileMover`: executes moves based on `proposal.proposed_destination` and logs operations identically.
- `organizer.operations.rollback.RollbackManager`: operates strictly on logged `Operation` records.
- `organizer.feedback.recorder.FeedbackRecorder`: collects `approved`/`rejected`/`modified` actions into the SQLite `feedback` table, which any tier can query for training data.
- `cli/commands/review.py` and `approve.py`: display proposals and collect user input with no knowledge of the producing backend.

### Where Tier 1 uses human feedback

The `feedback` table is the training corpus for Tier 1's kNN classifier.
`TrainingStore` (Stage 4) loads every `approved` / `modified` / `rejected`
row, re-extracts the source file's snippet, embeds it, and caches the vector
in memory. When a new file arrives, `EmbeddingClassifier` finds the top-K
nearest neighbors and returns the mode of their categories, weighted by
whether the neighbor came from real feedback (weight 1.0) or from bootstrap
pseudo-labels (weight 0.4). This is why every `[y]` / `[n]` / `[e]` in
`organizer review` silently improves future ML accuracy — there is no
separate training step, just an evolving feedback table.

---

## Test Data

Fixtures can be generated with `scripts/generate_test_data.py` (standard library only, no extra installs).

### Basic — 120 files in `./testdata`
```bash
python scripts/generate_test_data.py
```

### Deterministic (same layout every run — good for tests)
```bash
python scripts/generate_test_data.py --seed 42
```

### Bigger fixture, deeper nesting, with duplicate groups
```bash
python scripts/generate_test_data.py -n 500 --max-depth 6 --dupes 5 -o /tmp/bigfixture --clean
```

### Then drive the organizer against it
```bash
organizer scan testdata
organizer propose
organizer duplicates
organizer approve --dry-run
```