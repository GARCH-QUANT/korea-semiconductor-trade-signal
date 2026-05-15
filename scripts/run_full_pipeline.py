#!/usr/bin/env python3
"""
run_full_pipeline.py
串联 signals.py → events.py → report_generator.py → tg_message_formatter.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = [
    "signals.py",
    "events.py",
    "report_generator.py",
    "tg_message_formatter.py",
]


def run_script(script_name: str) -> int:
    path = BASE_DIR / "scripts" / script_name
    if not path.exists():
        print(f"[SKIP] {script_name} not found")
        return 0
    print(f"\n[RUN ] {script_name}")
    res = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr.strip():
        print(res.stderr.strip(), file=sys.stderr)
    return res.returncode


def main():
    failed = []
    for script in SCRIPTS:
        code = run_script(script)
        if code != 0:
            failed.append((script, code))

    print("\n" + "=" * 50)
    if not failed:
        print("✅ 全链路执行完成")
    else:
        print("❌ 以下阶段失败:")
        for script, code in failed:
            print(f"   {script}  exit={code}")
        sys.exit(1)


if __name__ == "__main__":
    main()
