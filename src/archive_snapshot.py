#!/usr/bin/env python3
"""
src/archive_snapshot.py
Creates a timestamped snapshot of all pipeline outputs for audit and reproducibility.
"""
from __future__ import annotations

import shutil
import hashlib
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = BASE_DIR / "data" / "archive"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR = BASE_DIR / "data" / "raw"


def file_hash(fp: Path) -> str:
    return hashlib.sha256(fp.read_bytes()).hexdigest()[:16]


def snapshot_metadata(processed_files: list[Path]) -> dict:
    return {
        "snapshot_ts": datetime.utcnow().isoformat(),
        "files": [
            {"name": fp.name, "hash": file_hash(fp), "size_bytes": fp.stat().st_size}
            for fp in processed_files
        ],
    }


def save_snapshot():
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snap_dir = ARCHIVE_DIR / ts
    snap_dir.mkdir(parents=True, exist_ok=True)

    processed_files = list(PROCESSED_DIR.glob("*.csv")) + list(PROCESSED_DIR.glob("*.md"))
    for fp in processed_files:
        shutil.copy2(fp, snap_dir / fp.name)

    meta = snapshot_metadata(processed_files)
    (snap_dir / "snapshot_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    print(f"[archive_snapshot] saved to {snap_dir}")
    return snap_dir


if __name__ == "__main__":
    save_snapshot()
