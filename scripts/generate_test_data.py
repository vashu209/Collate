#!/usr/bin/env python3
"""Generate a random nested directory tree of files for testing the organizer.

Usage:
    python scripts/generate_test_data.py
    python scripts/generate_test_data.py -o /tmp/fixture -n 500 --seed 42
    python scripts/generate_test_data.py --dupes 5 --clean
"""

import argparse
import random
import string
import sys
from pathlib import Path


# Name fragments grouped by rough category, used to build plausible filenames.
NAME_FRAGMENTS = {
    "academic": ["lecture", "assignment", "syllabus", "notes", "homework",
                 "midterm", "final_exam", "reading", "seminar", "workshop",
                 "BIO101", "CS229", "MATH51", "PHYS41"],
    "image":    ["vacation", "sunset", "portrait", "screenshot", "IMG_2024",
                 "DSC_0001", "family", "cat", "dog", "beach", "hike"],
    "archive":  ["backup", "project_snapshot", "release", "dataset",
                 "old_files", "photos_batch", "src"],
    "doc":      ["invoice", "resume", "cover_letter", "memo", "report",
                 "contract", "agenda", "todo", "recipe", "journal"],
    "project":  ["main", "utils", "test", "config", "readme", "setup",
                 "requirements", "pyproject", "package", "index"],
    "random":   ["data", "blob", "unknown", "temp", "scratch", "dump",
                 "log", "session", "cache", "output", "result"],
}

# Directory names. Some overlap with path_contains rules (.git, Semester, etc.).
DIR_POOLS = {
    "academic_dirs": ["Semester_2024_Fall", "Semester_2025_Spring", "Coursework",
                      "Lectures", "Assignments", "Readings", "Exams",
                      "CS229", "BIO101", "MATH51"],
    "media_dirs":    ["Photos", "Screenshots", "Camera", "Downloads", "Pictures"],
    "project_dirs":  ["my_project", ".git", "src", "tests", "docs", "build",
                      "node_modules", "venv", "dist"],
    "misc_dirs":     ["Misc", "Old", "Archive", "Inbox", "Temp", "Scratch",
                      "Documents", "Desktop", "shared"],
}

# Extensions per category.
EXT_BY_CATEGORY = {
    "academic": [".pdf", ".docx", ".pptx", ".txt", ".md", ".odt"],
    "image":    [".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".raw"],
    "archive":  [".zip", ".tar", ".gz", ".rar", ".7z"],
    "doc":      [".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx"],
    "project":  [".py", ".js", ".json", ".toml", ".yaml", ".yml", ".cfg"],
    "random":   [".dat", ".bin", ".log", ".tmp", ".xyz", ".foo"],
}


def rand_text(rng, min_words=3, max_words=30):
    """Random lowercase filler text."""
    words = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur",
             "adipiscing", "elit", "sed", "do", "eiusmod", "tempor",
             "incididunt", "ut", "labore", "magna", "aliqua", "enim",
             "minim", "veniam", "quis", "nostrud", "exercitation"]
    n = rng.randint(min_words, max_words)
    return " ".join(rng.choice(words) for _ in range(n))


def rand_bytes(rng, size):
    """Random bytes of the given size."""
    return bytes(rng.getrandbits(8) for _ in range(size))


def pick_name(rng, category):
    """Build a plausible base filename for a category."""
    pool = NAME_FRAGMENTS[category]
    style = rng.random()
    if style < 0.4:
        base = f"{rng.choice(pool)}_{rng.randint(1, 99)}"
    elif style < 0.7:
        base = f"{rng.choice(pool)}_{rng.choice(string.ascii_lowercase)}{rng.randint(1, 9)}"
    else:
        base = rng.choice(pool)
    # Occasionally vary casing to test case-insensitive matching.
    if rng.random() < 0.15:
        base = base.replace("_", " ").title()
    return base


def pick_category(rng):
    """Weighted random category, favoring academic and image."""
    cats = ["academic", "image", "archive", "doc", "project", "random"]
    weights = [3, 3, 1, 2, 2, 2]
    return rng.choices(cats, weights=weights, k=1)[0]


def build_tree(root, max_depth, rng):
    """Create nested directories and return all of them as a list."""
    root.mkdir(parents=True, exist_ok=True)
    dirs = [root]

    def recurse(parent, depth):
        if depth >= max_depth:
            return
        for _ in range(rng.randint(1, 3)):
            pool_key = rng.choice(list(DIR_POOLS.keys()))
            name = rng.choice(DIR_POOLS[pool_key])
            # Add a numeric suffix sometimes to avoid clashes.
            if rng.random() < 0.3:
                name = f"{name}_{rng.randint(1, 9)}"
            child = parent / name
            try:
                child.mkdir(exist_ok=True)
            except OSError:
                continue
            dirs.append(child)
            recurse(child, depth + 1)

    recurse(root, 0)
    return dirs


def make_file(target, ext, rng):
    """Write a file at target with content matching the extension."""
    target = target.with_name(target.name + ext)

    if ext in {".txt", ".md", ".log"}:
        text = rand_text(rng)
        if "lecture" in target.name.lower():
            text = "# Lecture Notes\n\n" + text
        target.write_text(text, encoding="utf-8")

    elif ext == ".py":
        target.write_text(
            '"""Generated test module."""\n\n'
            "def hello():\n"
            '    return "world"\n\n'
            "if __name__ == '__main__':\n"
            "    print(hello())\n",
            encoding="utf-8",
        )

    elif ext == ".js":
        target.write_text(
            "function hello() { return 'world'; }\nmodule.exports = { hello };\n",
            encoding="utf-8",
        )

    elif ext == ".json":
        target.write_text(
            '{"name": "fixture", "generated": true, "items": [1, 2, 3]}\n',
            encoding="utf-8",
        )

    elif ext in {".yaml", ".yml"}:
        target.write_text("version: 1\nitems:\n  - a\n  - b\n", encoding="utf-8")

    elif ext in {".toml", ".cfg"}:
        target.write_text("[tool]\nname = 'fixture'\nversion = '1.0'\n", encoding="utf-8")

    elif ext == ".csv":
        target.write_text("id,name,value\n1,alpha,10\n2,beta,20\n3,gamma,30\n", encoding="utf-8")

    elif ext in {".pdf", ".docx", ".pptx", ".xlsx", ".odt"}:
        # Real magic bytes so filetype can detect the format.
        magic = {
            ".pdf":  b"%PDF-1.4\n",
            ".docx": b"PK\x03\x04\x14\x00\x06\x00",
            ".pptx": b"PK\x03\x04\x14\x00\x06\x00",
            ".xlsx": b"PK\x03\x04\x14\x00\x06\x00",
            ".odt":  b"PK\x03\x04\x14\x00\x06\x00",
        }[ext]
        target.write_bytes(magic + rand_bytes(rng, rng.randint(256, 2048)))

    elif ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".raw"}:
        magic = {
            ".jpg":  b"\xff\xd8\xff\xe0",
            ".jpeg": b"\xff\xd8\xff\xe0",
            ".png":  b"\x89PNG\r\n\x1a\n",
            ".gif":  b"GIF89a",
            ".webp": b"RIFF\x00\x00\x00\x00WEBP",
            ".heic": b"\x00\x00\x00\x18ftypheic",
            ".raw":  b"",
        }[ext]
        target.write_bytes(magic + rand_bytes(rng, rng.randint(512, 4096)))

    elif ext in {".zip", ".tar", ".gz", ".rar", ".7z"}:
        magic = {
            ".zip": b"PK\x03\x04",
            ".tar": b"",
            ".gz":  b"\x1f\x8b\x08",
            ".rar": b"Rar!\x1a\x07",
            ".7z":  b"7z\xbc\xaf\x27\x1c",
        }[ext]
        target.write_bytes(magic + rand_bytes(rng, rng.randint(1024, 8192)))

    else:
        # Fallback for .dat, .bin, .tmp, .xyz, .foo, etc.
        target.write_bytes(rand_bytes(rng, rng.randint(16, 1024)))

    return target


def main():
    ap = argparse.ArgumentParser(
        description="Generate random test data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-o", "--output", default="testdata",
                    help="Root directory to create (default: ./testdata)")
    ap.add_argument("-n", "--num-files", type=int, default=120,
                    help="Number of files to generate (default: 120)")
    ap.add_argument("--max-depth", type=int, default=4,
                    help="Maximum directory nesting depth (default: 4)")
    ap.add_argument("--dupes", type=int, default=0,
                    help="Number of duplicate groups to add (identical content, different paths)")
    ap.add_argument("--seed", type=int, default=None,
                    help="Random seed for reproducibility")
    ap.add_argument("--clean", action="store_true",
                    help="Delete the output directory first if it exists")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    root = Path(args.output).expanduser().resolve()

    if args.clean and root.exists():
        import shutil
        shutil.rmtree(root)
        print(f"Cleaned {root}")

    if root.exists() and any(root.iterdir()):
        print(f"Warning: {root} is not empty; files will be added.", file=sys.stderr)

    print(f"Creating tree at: {root}")
    dirs = build_tree(root, max_depth=args.max_depth, rng=rng)
    print(f"  -> {len(dirs)} directories")

    created = []
    attempts = 0
    max_attempts = args.num_files * 10

    while len(created) < args.num_files and attempts < max_attempts:
        attempts += 1
        parent = rng.choice(dirs)
        category = pick_category(rng)
        ext = rng.choice(EXT_BY_CATEGORY[category])
        base_name = pick_name(rng, category)
        target = parent / base_name

        # Skip if this exact path already exists.
        if (parent / (base_name + ext)).exists():
            continue

        try:
            created.append(make_file(target, ext, rng))
        except OSError as e:
            print(f"  ! skipped {target}{ext}: {e}", file=sys.stderr)

    print(f"  -> {len(created)} files created")

    # Add known duplicate groups if requested.
    if args.dupes > 0:
        print(f"Creating {args.dupes} duplicate group(s)...")
        for i in range(args.dupes):
            parent = rng.choice(dirs)
            payload = rand_bytes(rng, rng.randint(256, 2048))
            ext = rng.choice([".txt", ".bin", ".dat"])
            for copy_idx in range(rng.randint(2, 4)):
                dest = parent / f"dup_{i}_{copy_idx}{ext}"
                dest.write_bytes(payload)
                created.append(dest)
        print(f"  -> {args.dupes} duplicate groups written")

    # Print a short summary.
    print("\nSummary by extension:")
    by_ext = {}
    for f in created:
        by_ext[f.suffix or "<none>"] = by_ext.get(f.suffix or "<none>", 0) + 1
    for ext, count in sorted(by_ext.items(), key=lambda kv: -kv[1]):
        print(f"  {ext:<10} {count:>4}")

    total_bytes = sum(f.stat().st_size for f in created if f.exists())
    print(f"\nTotal: {len(created)} files, {total_bytes:,} bytes")
    print(f"Root:  {root}")
    print("\nNext steps:")
    print(f"  organizer scan {root}")
    print(f"  organizer propose")
    print(f"  organizer duplicates")
    print(f"  organizer approve --dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())