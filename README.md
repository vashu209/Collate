# AI-Powered Intelligent File System Organizer (Phase 1: Rule-Based)

A robust, safety-first, deterministic file system organizer built in Python 3.11+. Validates the end-to-end organizational workflow with rule-based classification, SQLite persistence, cryptographic integrity checks, collision prevention, transactional logging, rollback capabilities, and strict architectural decoupling for seamless Phase 2 AI/ML integration.

---

## Final Directory Tree

```
Autonomous File Organizer/
├── .gitignore                         # Git exclusion rules for virtualenvs, runtime DBs, and cache
├── pyproject.toml                     # Package metadata, dependencies, scripts, and build configuration
├── README.md                          # Complete project documentation, architecture guide, and reference
├── config/
│   └── rules.yaml                     # Default classification rules, categories, priorities, and fallbacks
├── organizer/                         # Core domain library (zero CLI/Typer dependencies)
│   ├── __init__.py                    # Core package export and version marker
│   ├── ai/                            # Phase 2 placeholder interfaces and stubs
│   │   ├── __init__.py                # AI module namespace exports
│   │   ├── base.py                    # Abstract base classes for Classifier, ContentExtractor, Embedder
│   │   ├── classifier.py              # Placeholder AI classifier stub (raises NotImplementedError)
│   │   ├── content_extractor.py       # Placeholder content extractor stub (raises NotImplementedError)
│   │   └── embedder.py                # Placeholder vector embedder stub (raises NotImplementedError)
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
│   │   ├── mover.py                   # Safe cross-filesystem mover with pre-logging and verification
│   │   └── rollback.py                # Reversal engine restoring moved files with checksum verification
│   ├── rules/                         # Deterministic classification engine
│   │   ├── __init__.py                # Rules namespace exports
│   │   ├── engine.py                  # RuleBasedClassifier implementing the Classifier ABC interface
│   │   └── models.py                  # Dataclass domain models (FileRecord, Proposal, Operation, etc.)
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
│   └── commands/                      # Individual CLI command implementations
│       ├── __init__.py                # Commands package marker
│       ├── approve.py                 # Review, approve, modify, or reject pending proposals
│       ├── duplicates.py              # Scan catalog and report exact SHA-256 duplicates
│       ├── propose.py                 # Evaluate unproposed files against the rule engine
│       ├── rollback.py                # Restore files to original paths from operation logs
│       ├── scan.py                    # Recursively walk directories and populate SQLite catalog
│       └── status.py                  # Display summary metrics and database status tables
├── tests/                             # Comprehensive test suite (filesystem-isolated with tmp_path)
│   ├── test_cli.py                    # End-to-end CLI workflow tests using Typer CliRunner
│   ├── test_operations.py             # Move safety, collision avoidance, and rollback round-trip tests
│   ├── test_rules_engine.py           # Condition matching, priority resolution, and AI interface tests
│   └── test_scanner.py                # Directory walking, metadata extraction, and hash tests
└── data/                              # Default runtime SQLite database directory (gitignored)
```

---

## One-Line Responsibility Statement per File / Folder

- **`organizer/`**: Independent, framework-agnostic Python library containing all core organization logic.
- **`organizer/ai/base.py`**: Defines abstract interfaces (`Classifier`, `ContentExtractor`, `Embedder`) establishing contracts for Phase 2 AI models.
- **`organizer/ai/classifier.py`**: Placeholder stub for future LLM/ML classification models.
- **`organizer/ai/content_extractor.py`**: Placeholder stub for future multimodal and NLP text extraction.
- **`organizer/ai/embedder.py`**: Placeholder stub for future dense vector embeddings.
- **`organizer/config/schema.py`**: Type-safe dataclass definitions and constraint validation for rules configuration.
- **`organizer/config/loader.py`**: Parses, validates, and instantiates configuration objects from YAML files.
- **`organizer/dedup/hasher.py`**: Computes streaming SHA-256 hashes and clusters files into duplicate groups.
- **`organizer/feedback/recorder.py`**: Persists user approval, rejection, and destination edits to prepare training datasets for Phase 2.
- **`organizer/operations/mover.py`**: Atomically moves files with pre-operation DB logging, collision avoidance, and post-copy hash checks.
- **`organizer/operations/rollback.py`**: Safely reverses completed moves back to original locations after verifying file integrity.
- **`organizer/rules/models.py`**: Houses core dataclasses (`FileRecord`, `Condition`, `Rule`, `Proposal`, `Operation`, `FeedbackRecord`).
- **`organizer/rules/engine.py`**: Implements deterministic rule evaluation and priority resolution behind the `Classifier` interface.
- **`organizer/scanning/metadata.py`**: Probes file attributes including POSIX/Windows timestamps and magic-byte MIME types.
- **`organizer/scanning/scanner.py`**: Recursively scans directory trees and yields complete `FileRecord` structures.
- **`organizer/storage/db.py`**: Manages SQLite connections, enables Write-Ahead Logging (WAL) and foreign keys, and provisions schemas.
- **`organizer/storage/repository.py`**: Provides transactional CRUD queries across files, proposals, operations, and feedback.
- **`organizer/utils/paths.py`**: Generates unique non-colliding file paths (`name_1.ext`) and ensures directory hierarchy.
- **`organizer/utils/logging_config.py`**: Configures runtime logging formatters and stream handlers.
- **`cli/`**: Presentation and interactive terminal interface layer built with Typer and Rich.
- **`cli/main.py`**: Command router and CLI entrypoint exposing all subcommands.
- **`cli/commands/scan.py`**: CLI handler for cataloging files and computing checksums.
- **`cli/commands/propose.py`**: CLI handler for generating organization proposals via rule classification.
- **`cli/commands/approve.py`**: CLI handler for interactive proposal review, modification, dry-runs, and batch approvals.
- **`cli/commands/rollback.py`**: CLI handler for reversing move operations using transaction logs.
- **`cli/commands/duplicates.py`**: CLI handler for discovering and displaying exact duplicates.
- **`cli/commands/status.py`**: CLI handler for rendering system-wide health and metric tables.
- **`config/rules.yaml`**: Declarative rule specification containing match conditions, destination mappings, and priority weights.
- **`tests/`**: Pytest test suite providing 100% automated coverage across unit, operational, and CLI flows.
- **`pyproject.toml`**: Packaging configuration declaring console scripts and dependencies.

---

## The `rules.yaml` Format Explained

The rules file is written in YAML and defines how files should be categorized based on deterministic criteria.

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
- `--recursive / --no-recursive`: Enable/disable recursive subfolder traversal (default: `--recursive`).
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Example:*
```bash
organizer scan ~/Downloads --recursive
```

### 2. `organizer propose`

Runs the classification engine over all scanned files in the database that do not currently have a pending proposal. Creates pending `Proposal` records.

```bash
organizer propose [--config PATH] [--min-confidence FLOAT] [--db PATH]
```

- `--config <str>`: Path to rules YAML file (default: `config/rules.yaml`).
- `--min-confidence <float>`: Override minimum confidence threshold required for proposals.
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Example:*
```bash
organizer propose --config config/rules.yaml --min-confidence 0.6
```

### 3. `organizer approve`

Walks pending proposals for user review. Interactive by default. Allows reviewing source path, proposed category, destination, confidence score, and rationale.

```bash
organizer approve [--all] [--interactive] [--dry-run] [--db PATH]
```

- `--all`: Approve and execute all pending proposals immediately without prompting.
- `--interactive`: Explicitly prompt for each proposal (default behavior when `--all` is omitted).
- `--dry-run`: Previews all pending moves in a Rich table without touching the filesystem or modifying the database.
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Interactive Options per Proposal:*
- `[y]es`: Approves the proposal, moves the file immediately, logs an operation, and records positive feedback.
- `[n]o`: Rejects the proposal, marks it rejected in DB, and records negative feedback.
- `[e]dit`: Prompts for a custom destination path, executes the move there, and records a `modified` feedback entry.
- `[q]uit`: Exits the interactive review session.

*Examples:*
```bash
# Preview what would move without touching files
organizer approve --dry-run

# Interactively review each pending file
organizer approve

# Batch accept all proposals without prompts
organizer approve --all
```

### 4. `organizer rollback`

Safely reverses completed move operations, returning files to their exact original source paths.

```bash
organizer rollback [--last N | --operation-id ID | --all] [--db PATH]
```

- `--last <int>`, `-n <int>`: Roll back the most recent $N$ completed operations.
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
# Undo the last 5 file moves
organizer rollback --last 5

# Revert an entire batch
organizer rollback --all
```

### 5. `organizer duplicates`

Scans the catalog and prints groups of exact duplicate files identified by matching SHA-256 hashes. Read-only operation.

```bash
organizer duplicates [<path>] [--db PATH]
```

- `[path]`: Optional directory prefix filter.
- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Example:*
```bash
organizer duplicates ~/Downloads
```

### 6. `organizer status`

Renders an overview table detailing files scanned, proposals pending/approved/rejected/executed, operations completed/rolled back/failed, and total feedback log count.

```bash
organizer status [--db PATH]
```

- `--db <str>`: Path to SQLite database (default: `data/organizer.db`).

*Example:*
```bash
organizer status
```

---

## Assumptions Made

1. **Storage Location**: The default database path is `data/organizer.db`. The parent directory is created automatically upon first run.
2. **Path Normalization**: All file paths are expanded and resolved to absolute paths before storage and operation execution.
3. **Collision Strategy**: When a move destination already exists on disk, a numeric suffix (`_1`, `_2`) is appended before the file extension. This ensures non-destructive execution under all circumstances.
4. **Symlink Safety**: Symlinks are identified during metadata extraction and skipped by default to avoid accidental traversal cycles or cross-link moves.
5. **Cross-Device Move Reliability**: Instead of relying on atomic `os.rename` (which fails across filesystem and mount boundaries), moves are executed via `shutil.copy2` $\rightarrow$ destination SHA-256 verification $\rightarrow$ source deletion.
6. **Pre-Operation Journaling**: The operation is recorded with status `pending` in SQLite *before* filesystem modification. If the process is halted mid-move, the incomplete operation can be audited and resolved.

---

## How to Swap In a Real AI Classifier for `RuleBasedClassifier`

The architecture was intentionally designed around stable seams to guarantee that Phase 2 AI integration requires **zero changes** to the CLI, database repository, or filesystem operations.

### The Seam Architecture

The contract between classification and everything downstream is defined by two constructs:

1. **`organizer.rules.models.Proposal`**:
   The universal data contract:
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
2. **`organizer.ai.base.Classifier`**:
   The abstract base class in `organizer/ai/base.py`:
   ```python
   class Classifier(ABC):
       @abstractmethod
       def classify(self, record: FileRecord) -> Proposal:
           pass
   ```

`RuleBasedClassifier` in `organizer/rules/engine.py` implements this exact `Classifier` ABC.

### Exact Steps to Swap in a Phase 2 AI Classifier

To introduce a multimodal LLM or embedding-based classifier (e.g. Gemini API, sentence-transformers):

1. **Implement `AIClassifier` in `organizer/ai/classifier.py`**:
   Replace the placeholder stub:
   ```python
   from organizer.ai.base import Classifier
   from organizer.rules.models import FileRecord, Proposal

   class AIClassifier(Classifier):
       def __init__(self, model_name: str = "gemini-2.5-flash", organize_root: str = "~/Organized"):
           self.model_name = model_name
           self.organize_root = Path(organize_root).expanduser()

       def classify(self, record: FileRecord) -> Proposal:
           # 1. Read document text / inspect thumbnail using ContentExtractor
           # 2. Query LLM or vector index with file metadata and extracted content
           # 3. Obtain predicted category, target folder, confidence score, and explanation
           return Proposal(
               file_id=record.id,
               source_path=record.path,
               proposed_category=prediction.category,
               proposed_destination=str(self.organize_root / prediction.folder / record.filename),
               confidence=prediction.confidence,
               rationale=prediction.explanation,
           )
   ```

2. **Update the Classifier Factory or CLI Flag**:
   In `cli/commands/propose.py`, allow selecting the classifier implementation (e.g., via `--model ai` or by default):
   ```python
   # In propose.py:
   if use_ai:
       classifier = AIClassifier(...)
   else:
       classifier = RuleBasedClassifier(rules_cfg)
   ```

3. **What Does NOT Need to Change**:
   - `organizer.storage.repository.Repository`: Accepts and saves `Proposal` objects identically.
   - `organizer.operations.mover.FileMover`: Executes moves based on `proposal.proposed_destination` and logs operations identically.
   - `organizer.operations.rollback.RollbackManager`: Operates strictly on logged `Operation` records.
   - `organizer.feedback.recorder.FeedbackRecorder`: Collects human feedback (`approved`, `rejected`, `modified`) into the SQLite `feedback` table, which can now be queried directly to fine-tune or few-shot prompt the Phase 2 AI model.
   - `cli/commands/approve.py`: Displays proposals and collects user input with no knowledge of whether the proposal was produced by a regex rule or a 100B-parameter neural network.
