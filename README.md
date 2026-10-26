# Autonomous File Organizer (Collate)

A robust, safety-first file system organizer built in Python 3.11+.

It is a command-line utility for categorizing, deduplicating, and safely
relocating files. It guarantees zero data loss through transactional SQLite
journaling and cryptographic verification.

Classification is driven by a **capability ladder**: multiple backends
implement the same `Classifier` interface and are selected at runtime.
Today the default is the deterministic rule engine (Tier 0). A local
sentence-embedding backend (Tier 1) is in progress; a small local LLM tier
(Tier 2) and a cloud-API tier (Tier 3) are planned. See
[DEVELOPER.md § Classification Tiers](DEVELOPER.md#classification-tiers-and-development-stages)
for the full roadmap.

## Core Philosophy

- **Safety First**: Filesystem modifications are journaled in an SQLite
  database before execution. If a process is interrupted, the filesystem can
  be perfectly rolled back to its prior state.
- **Zero Data Loss**: Cryptographic SHA-256 integrity checks ensure a source
  file is only deleted after mathematical verification that it arrived at its
  destination intact.
- **Backend-Agnostic Architecture**: The CLI, database, and filesystem
  operations consume `Proposal` objects produced by any classifier backend
  and have no knowledge of which one is running.

## Key Features

- **Interactive Review**: Paginated, filterable terminal UI to review,
  approve, edit, skip, or reject proposals before execution.
- **Bulk Operations**: Approve all, approve by category, approve by display-ID
  range, or filter to a single category.
- **Dry Runs**: Preview every pending move without touching the filesystem or
  database.
- **Transactional Rollbacks**: Revert the last N operations, a specific
  operation, or everything, via database logs.
- **Duplicate Detection**: Identify exact duplicates using chunked SHA-256
  hashing.
- **Collision Prevention**: Automatically handle duplicate destination
  filenames with non-destructive suffixes (e.g., `file_1.pdf`).
- **Date Bucketing**: Files land in a `YYYY-MM-DD` subfolder once the category
  folder already exists, so recurring imports stay chronological.

---

## Installation

Requires **Python 3.11+**. Recommended to install within a virtual environment.

```bash
git clone https://github.com/yourusername/collate.git
cd collate
pip install -e .
```

This registers the global console script `organizer`.

Optional extras:

```bash
# Needed for the in-progress ML tier (Tier 1)
pip install -e ".[ml]"

# Needed to run the test suite
pip install -e ".[dev]"
```

After installing `[ml]`, fetch the model files once per machine:

```bash
python scripts/fetch_ml_model.py
```

---

## Quick Start

1. **Scan the target directory** — extracts metadata and hashes, saving them
   to the local SQLite database:

   ```bash
   organizer scan ~/Downloads --recursive
   ```

2. **Generate move proposals** — evaluates files against the configured rules
   (or another backend) and queues proposed destinations:

   ```bash
   organizer propose
   ```

3. **Review and approve changes** — paginated interactive UI to approve
   `[y]`, reject `[n]`, edit `[e]`, skip `[s]`, or inspect `[v]` each
   proposal:

   ```bash
   organizer review
   ```

4. *(Optional)* **Roll back recent moves** if something went wrong:

   ```bash
   organizer rollback --last 5
   ```

---

## Classification Backends

`organizer propose` supports multiple classification backends, selected with
`--model`. The available tiers are:

- **`rules`** (default today) — deterministic, always available. No
  dependencies beyond the base install.
- **`ml`** (in progress) — local sentence embeddings (MiniLM-L6-v2 via ONNX,
  quantized). Install with `pip install 'file-organizer[ml]'` and fetch the
  model with `python scripts/fetch_ml_model.py`. Runs on CPU; no GPU
  required.
- **`llm`** (planned) — local small-LLM classification for ambiguous files.
  Requires a dGPU for acceptable throughput.
- **`api`** (planned) — cloud LLM classification, opt-in only. Requires an
  API key.

Tiers that are unavailable on the current machine are reported by the CLI with
a reason. If a requested tier can't run, the tool falls back to `rules`
automatically unless `--no-fallback` is passed.

See [DEVELOPER.md § Classification Tiers](DEVELOPER.md#classification-tiers-and-development-stages)
for the full roadmap and the stage-by-stage build plan for Tier 1.

---

## Configuration (`rules.yaml`)

The configuration file (`config/rules.yaml`) defines deterministic
categorization rules. It is also used by the ML tier to seed its bootstrap
pseudo-labels on first run.

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

### Rule Processing

- **Match Types**: Supports matching by `extension`, `keyword_in_name`, and
  `path_contains` (all case-insensitive).
- **Conflict Resolution**: If a file matches multiple rules, the rule with the
  highest `priority` wins. On a tie, the highest `confidence` breaks it.
- **Fallbacks**: Files matching no rules or falling below
  `min_confidence_for_proposal` are routed to `unmatched_destination`.

---

## Command Reference

### `scan`

Extracts filesystem metadata, calculates SHA-256 checksums, and updates the
catalog.

```bash
organizer scan <path> [--recursive / --no-recursive] [--db PATH]
```

`--recursive` defaults to off; pass it explicitly for subfolder traversal.

### `propose`

Runs the classification backend over scanned files to generate pending move
proposals.

```bash
organizer propose [--config PATH] [--min-confidence FLOAT]
                  [--organize-root PATH] [--db PATH]
```

`--organize-root` overrides the base directory for organized folders. When
omitted, the most recently scanned root is used.

*(A `--model rules|ml|llm|api` flag lands with Tier 1 Stage 5; today the
rules engine is the only backend.)*

### `approve` / `review`

Review, approve, edit, skip, or reject pending proposals. `approve` is an
alias that delegates to `review` and accepts the same flags.

```bash
organizer review [--all] [--approve-category CATEGORY] [--approve-range RANGE]
                 [--filter-category CATEGORY] [--page-size N]
                 [--dry-run] [--db PATH]
```

- `--all` — approve and execute every pending proposal without prompting.
- `--approve-category` — bulk approve a single category.
- `--approve-range` — bulk approve display-ID indices (e.g., `1-15`, `1,4,7`).
- `--filter-category` — restrict the session to one category.
- `--page-size` — rows per page (default 20).
- `--dry-run` — preview without touching the filesystem or database.

In the interactive paginated view, commands include `y <id|range>`,
`n <id|range>`, `e <id>`, `v <id>`, `s <id>`, `sa` (skip page), `sc <category>`,
`sr <range>`, `b`/`n` (previous/next page), `ps <size>`, and `q` to quit.

### `rollback`

Safely reverse completed move operations, returning files to original paths.

```bash
organizer rollback [--last N | --operation-id ID | --all] [--db PATH]
```

Rollback verifies the destination file's SHA-256 still matches the original
operation checksum before restoring; corrupted or edited files are refused to
prevent data loss.

### `duplicates`

Scan the catalog to report exact duplicate files based on SHA-256 hashes.
Read-only.

```bash
organizer duplicates [<path>] [--db PATH]
```

### `status`

View summary metrics and database status tables.

```bash
organizer status [--db PATH]
```

---

## Further Documentation

- **[Developer Guide (DEVELOPER.md)](DEVELOPER.md)** — Architecture, the
  classification-tier ladder, the stage-by-stage build plan for Tier 1, and
  the plug-in seam for adding a new classifier backend without touching the
  CLI, storage, or operations layers.
- **[Test Data Generator](scripts/generate_test_data.py)** — Generate nested
  directory trees with categorized files for local testing. Standard library
  only; no extra installs.