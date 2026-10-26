# Autonomous File Organizer (Collate)

A robust, safety-first file system organizer built in Python 3.11+.

It is a command-line utility for categorizing, deduplicating, and safely
relocating files. It guarantees zero data loss through transactional SQLite
journaling and cryptographic verification.

Classification is driven by a **capability ladder**: multiple backends
implement the same `Classifier` interface and are selected at runtime. The
default backend is a local sentence-embedding classifier (Tier 1, MiniLM-L6-v2
via ONNX) that learns from your review decisions. It runs on any CPU with no
GPU required. A deterministic rule engine (Tier 0) is always available as a
fallback and requires no extra installation. A local LLM tier (Tier 2) and a
cloud-API tier (Tier 3) are planned. See
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

- **ML-Backed Classification**: Local embeddings learn from your review
  decisions (accept / reject / edit) and improve over time. No GPU, no API
  keys, no cloud.
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

This registers the global console script `organizer`. The base install
includes the deterministic rule engine (Tier 0) and works out of the box.

### Optional: ML classifier (Tier 1)

The local ML backend needs four dependencies and a one-time model download:

```bash
pip install -e ".[ml]"
python scripts/fetch_ml_model.py
```

The fetch script downloads ~90 MB of quantized MiniLM files from HuggingFace,
verifies their SHA-256 hashes, and installs them into
`organizer/ai/models/minilm-l6-v2/`. It is idempotent — safe to re-run.

Once installed, `organizer propose` defaults to `--model ml`. If the model
files or dependencies are missing, the tool falls back to `rules` with a
clear message.

### Optional: development

```bash
pip install -e ".[dev]"
```

Adds `pytest` for running the test suite.

---

## Quick Start

1. **Scan the target directory** — extracts metadata and hashes, saving them
   to the local SQLite database:

   ```bash
   organizer scan ~/Downloads --recursive
   ```

2. **Generate move proposals** — runs the ML classifier (or another backend,
   via `--model`) and queues proposed destinations. On a fresh database with
   no review history, the ML tier auto-bootstraps from the rules engine so it
   has something to work with on the first run:

   ```bash
   organizer propose
   ```

3. **Review and approve changes** — paginated interactive UI to approve
   `[y]`, reject `[n]`, edit `[e]`, skip `[s]`, or inspect `[v]` each
   proposal. Every decision feeds back into the ML training corpus:

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

- **`ml`** (default) — local sentence embeddings (MiniLM-L6-v2 via ONNX,
  quantized). Install with `pip install 'file-organizer[ml]'` and fetch the
  model with `python scripts/fetch_ml_model.py`. Runs on CPU; no GPU
  required. Learns from your review decisions.
- **`rules`** — deterministic rule engine. Always available; no extra
  dependencies beyond the base install. Useful for reproducible categorization
  or when the ML tier isn't installed.
- **`llm`** (planned) — local small-LLM classification for ambiguous files.
  Requires a dGPU for acceptable throughput.
- **`api`** (planned) — cloud LLM classification, opt-in only. Requires an
  API key.

Tiers that are unavailable on the current machine are reported by the CLI with
a reason. If a requested tier can't run, the tool falls back to `rules`
automatically unless `--no-fallback` is passed.

See [DEVELOPER.md § Classification Tiers](DEVELOPER.md#classification-tiers-and-development-stages)
for the full roadmap.

---

## Configuration (`rules.yaml`)

The configuration file (`config/rules.yaml`) defines deterministic
categorization rules. The ML tier uses the same rules to seed bootstrap
pseudo-labels on first run, and an optional `ml:` block tunes its behavior.

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

# Optional. If omitted, ML uses the defaults shown here.
ml:
  k: 5
  pseudo_weight: 0.4
  min_confidence_for_proposal: 0.55
```

### Rule Processing

- **Match Types**: Supports matching by `extension`, `keyword_in_name`, and
  `path_contains` (all case-insensitive).
- **Conflict Resolution**: If a file matches multiple rules, the rule with the
  highest `priority` wins. On a tie, the highest `confidence` breaks it.
- **Fallbacks**: Files matching no rules or falling below
  `min_confidence_for_proposal` are routed to `unmatched_destination`.

---

## Tuning the ML tier

The `ml:` block in `rules.yaml` controls the ML classifier's behavior:

- **`k`** (`int`, default `5`) — how many nearest neighbors vote on the
  category. Higher K = more stable but slower to reflect new decisions;
  lower K = more reactive but noisier. The default of 5 is the standard for
  text kNN.
- **`pseudo_weight`** (`float`, default `0.4`) — how much a rules-derived
  bootstrap example counts relative to a real user review decision.
  Concretely, three pseudo-labeled examples (each weighted 0.4) lose to two
  real approvals (each weighted 1.0) in the vote. Keep it below ~0.7 or ML
  can't improve over rules as feedback accumulates.
- **`min_confidence_for_proposal`** (`float`, default `0.55`) — the vote-share
  threshold below which the file routes to `_Uncategorized`. This is
  **separate** from `defaults.min_confidence_for_proposal` (which governs the
  rules tier). The two tiers measure confidence differently — rules confidence
  is a hand-authored static weight; ML confidence is a measured vote share —
  and shouldn't share a threshold.

The ML confidence number is the **vote share** of the winning category among
the top-K neighbors, not the raw similarity of the nearest one. A unanimous
5/5 vote gives confidence ~1.0 even if the individual similarities are
moderate; a 3/2 split gives ~0.6 even if the nearest neighbor is very close.
The top-1 similarity is printed in the rationale as a secondary signal.

See [DEVELOPER.md § Tier 1 tuning and design decisions](DEVELOPER.md#tier-1-tuning-and-design-decisions)
for the reasoning and how to tune.

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

Runs the selected classification backend over scanned files to generate
pending move proposals.

```bash
organizer propose [--model {rules|ml|llm|api}]
                  [--config PATH] [--min-confidence FLOAT]
                  [--organize-root PATH] [--no-fallback] [--db PATH]
```

- `--model` — backend tier. Default `ml`; falls back to `rules` if the tier
  is unavailable, unless `--no-fallback` is set.
- `--config` — path to `rules.yaml` (default: `config/rules.yaml`).
- `--min-confidence` — overrides `defaults.min_confidence_for_proposal` for
  the rules tier. The ML tier reads `ml.min_confidence_for_proposal` from the
  config instead.
- `--organize-root` — base directory for organized folders. Defaults to the
  most recently scanned root.
- `--no-fallback` — fail hard if the requested tier is unavailable, instead
  of degrading to `rules`.

On a fresh database with no review history, `--model ml` auto-bootstraps
from the rules engine: existing files are pseudo-labeled so the ML tier has
training data, then classified. The bootstrap count is printed.

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

Every `[y]` / `[n]` / `[e]` decision is logged to the `feedback` table and
used as training data for the next `propose --model ml` run.

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
  classification-tier ladder, the tuning rationale for the ML tier, the
  propose-service seam, and the plug-in path for adding a new classifier
  backend without touching the CLI, storage, or operations layers.
- **[Test Data Generator](scripts/generate_test_data.py)** — Generate nested
  directory trees with categorized files for local testing. Standard library
  only; no extra installs.