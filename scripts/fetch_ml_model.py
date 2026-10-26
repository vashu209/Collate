#!/usr/bin/env python3
"""Download and verify MiniLM ONNX files for the Tier 1 ML classifier.

Run once per machine:

    python scripts/fetch_ml_model.py

Fetches from HuggingFace's Xenova/all-MiniLM-L6-v2 ONNX mirror:

  - model.onnx      (quantized int8, ~90 MB)
  - tokenizer.json  (~700 KB)
  - config.json     (~500 B)

Installs into organizer/ai/models/minilm-l6-v2/ and prints SHA-256 hashes so
they can be pinned in EXPECTED_SHA256. Idempotent: skips files that already
exist with matching hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

BASE_URL = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main"

FILES = {
    "model.onnx":     f"{BASE_URL}/onnx/model_quantized.onnx",
    "tokenizer.json": f"{BASE_URL}/tokenizer.json",
    "config.json":    f"{BASE_URL}/config.json",
}

# Populated after first run. When a hash is present, verification is strict.
EXPECTED_SHA256: dict[str, str] = {}

DEST_DIR = Path(__file__).parent.parent / "organizer" / "ai" / "models" / "minilm-l6-v2"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    print(f"  downloading {url}")
    with urllib.request.urlopen(url) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--force", action="store_true", help="Re-download even if files exist")
    ap.add_argument("--dest", default=str(DEST_DIR), help=f"Install dir (default: {DEST_DIR})")
    args = ap.parse_args()

    dest = Path(args.dest).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Installing MiniLM into: {dest}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for name, url in FILES.items():
            final = dest / name

            if final.exists() and not args.force:
                observed = sha256_of(final)
                expected = EXPECTED_SHA256.get(name)
                if expected is None or observed == expected:
                    print(f"  skip {name} (already present, sha256={observed[:16]}...)")
                    continue
                print(f"  re-downloading {name} (sha256 mismatch)")
                final.unlink()

            staging = tmp / name
            try:
                download(url, staging)
            except Exception as e:
                print(f"  ERROR downloading {name}: {e}", file=sys.stderr)
                return 1

            observed = sha256_of(staging)
            expected = EXPECTED_SHA256.get(name)
            if expected and observed != expected:
                print(
                    f"  ERROR sha256 mismatch for {name}\n"
                    f"    expected: {expected}\n"
                    f"    observed: {observed}",
                    file=sys.stderr,
                )
                return 1

            print(f"  {name}: sha256={observed}")
            if not expected:
                print(f"    (pin with EXPECTED_SHA256['{name}'] = '{observed}')")

            shutil.move(str(staging), str(final))

    print("\nVerifying capabilities...")
    print('  python -c "from organizer.ai.capabilities import detect_capabilities; print(detect_capabilities())"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())