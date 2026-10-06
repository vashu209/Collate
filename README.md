# Autonomous File Organizer (Collate)

A robust, safety-first, deterministic file system organizer built in Python 3.11+.

It is a command-line utility for categorizing, deduplicating, and safely relocating files. It guarantees zero data loss through transactional SQLite journaling and cryptographic verification.

The project is currently in **Phase 1 (Rule-Based)**, operating on deterministic criteria such as file extensions, filename keywords, and path substrings.

The architecture is strictly decoupled to prepare for **Phase 2 (AI Integration)**. The filesystem manipulation, database logging, and collision resolution layers are abstracted behind a common interface. This allows Phase 2 multimodal AI/ML models to be swapped in as the classification engine without requiring structural changes to the core application.

## Core Philosophy

- **Safety First**: Filesystem modifications are journaled in an SQLite database before execution. If a process is interrupted, the filesystem can be perfectly rolled back to its prior state.
- **Zero Data Loss**: Cryptographic SHA-256 integrity checks ensure a source file is only deleted after mathematical verification that it arrived at its destination intact.
- **AI-Ready Architecture**: The CLI, database, and filesystem operations are fully decoupled from the classification engine.

## Key Features

- **Interactive Approvals**: Review every proposed file move in the terminal before execution.
- **Dry Runs**: Test rule configurations without modifying the filesystem.
- **Transactional Rollbacks**: Revert the last $N$ operations via database logs.
- **Duplicate Detection**: Identify exact duplicates using chunked SHA-256 hashing.
- **Collision Prevention**: Automatically handle duplicate destination filenames with non-destructive suffixes (e.g., `file_1.pdf`).

---

## Installation

Requires **Python 3.11+**. It is recommended to install the tool within a virtual environment.

```bash
git clone https://github.com/yourusername/collate.git
cd collate
pip install -e .
```
This registers the global console script `organizer`.

---

## Quick Start

1. **Scan the target directory**:
   Extracts metadata and hashes, saving them to the local SQLite database.
   ```bash
   organizer scan ~/Downloads
   ```
2. **Generate move proposals**:
   Evaluates files against the configured rules and queues proposed destinations.
   ```bash
   organizer propose
   ```
3. **Review and approve changes**:
   Opens an interactive terminal prompt to approve `[y]`, reject `[n]`, or modify `[e]` each destination.
   ```bash
   organizer approve --interactive
   ```
*(Note: To reverse recent operations, use `organizer rollback --last N`)*

---

## Configuration (`rules.yaml`)

The configuration file (`config/rules.yaml`) defines deterministic categorization rules.

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
- **Match Types**: Supports matching by `extension`, `keyword_in_name`, and `path_contains` (case-insensitive).
- **Conflict Resolution**: If a file matches multiple rules, the rule with the highest `priority` takes precedence. In the event of a tie, the highest `confidence` score is selected.
- **Fallbacks**: Files matching no rules or falling below `min_confidence_for_proposal` are routed to `unmatched_destination`.

---

## Command Reference

### `scan`
Extracts filesystem metadata, calculates SHA-256 checksums, and updates the catalog.
```bash
organizer scan <path> [--recursive / --no-recursive] [--db PATH]
```

### `propose`
Runs the classification engine over scanned files to generate pending move proposals.
```bash
organizer propose [--config PATH] [--min-confidence FLOAT] [--db PATH]
```

### `approve`
Review, accept, edit, or reject pending proposals.
```bash
organizer approve [--all] [--interactive] [--dry-run] [--db PATH]
```

### `rollback`
Safely reverse completed move operations, returning files to original paths.
```bash
organizer rollback [--last N | --operation-id ID | --all] [--db PATH]
```

### `duplicates`
Scan the catalog to report exact duplicate files based on SHA-256 hashes. Read-only.
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

- **[Developer Guide (DEVELOPER.md)](DEVELOPER.md)**: Architectural documentation, directory structures, and instructions for implementing Phase 2 AI classifiers.
