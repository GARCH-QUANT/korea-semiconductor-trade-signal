#!/usr/bin/env python3
"""
src/generate_dual_section_report.py
Generates a two-section markdown report: SSD first, then HBM.
Assumes signals.py has already tagged records with signal_group (SSD / HBM / UNMAPPED).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import sys

BASE_DIR    = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from report_generator import run as generate_report

OUT_FILE = BASE_DIR / "data" / "processed" / "trade_signal_dual_report.md"


def section_block(title: str, df: pd.DataFrame) -> str:
    if df.empty:
        return f"## {title}\n\n*No signals in this category.*\n\n"
    lines = [f"## {title}", ""]
    cols = [c for c in ["hs_code", "stat_date", "signal_type",
                         "signal_score", "signal_grade",
                         "price_qty_mom", "qty_mom", "value_mom"]
            if c in df.columns]
    lines.append(df[cols].to_markdown(index=False))
    lines.append("")
    return "\n".join(lines)


def build_dual(signal_df: pd.DataFrame) -> str:
    parts = [
        "# Korea Semiconductor Trade Signal — Dual Section Report\n",
        "*SSD · HBM · Automated · GARCH-QUANT*\n\n",
        "---\n\n",
    ]
    for group, title in [("SSD", "SSD (Solid-State Drives)"),
                          ("HBM", "HBM (High-Bandwidth Memory)")]:
        sub = signal_df[signal_df.get("signal_group", pd.Series()) == group]
        parts.append(section_block(title, sub))
        parts.append("---\n\n")
    return "".join(parts)


def main():
    # Run the base report to populate signal_master.csv
    generate_report()

    signal_file = BASE_DIR / "data" / "processed" / "signal_master.csv"
    df = pd.read_csv(signal_file) if signal_file.exists() else pd.DataFrame()

    report = build_dual(df)
    OUT_FILE.write_text(report, encoding="utf-8")
    print(f"[generate_dual_section_report] written: {OUT_FILE}")
    return OUT_FILE


if __name__ == "__main__":
    main()
