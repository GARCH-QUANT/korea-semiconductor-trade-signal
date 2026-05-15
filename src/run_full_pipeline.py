#!/usr/bin/env python3
"""
src/run_full_pipeline.py
Delegates to scripts/run_full_pipeline.py for the actual 4-stage pipeline execution.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
TARGET = SCRIPTS_DIR / "run_full_pipeline.py"


def main():
    """Run the 4-stage pipeline: signals → events → report → tg_format."""
    print(f"[run_full_pipeline] delegating to {TARGET}")
    res = subprocess.run(
        [sys.executable, str(TARGET)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )
    if res.stdout:
        print(res.stdout)
    if res.returncode != 0 and res.stderr:
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
