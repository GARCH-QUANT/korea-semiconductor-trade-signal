#!/usr/bin/env python3
"""
src/alert_router.py
Routes signal alerts to Telegram based on grade thresholds.
Reads signal_master.csv and sends formatted alerts for A/B/C grade signals.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "")
SIGNAL_FILE  = BASE_DIR / "data" / "processed" / "signal_master.csv"

GRADE_THRESHOLDS = {"A": 3, "B": 2, "C": 1}   # send alert for grade >= C


def grade_priority(grade: str) -> int:
    return GRADE_THRESHOLDS.get(grade, -999)


def format_alert_row(row: pd.Series) -> str:
    lines = [
        f"▸ {row.get('signal_group','N/A')} | {row.get('hs_code','N/A')}",
        f"  Grade: {row.get('signal_grade','?')} | Score: {row.get('signal_score','?')}",
        f"  Type: {row.get('signal_type','mixed')}",
        f"  Price MoM: {row.get('price_qty_mom','N/A')}",
        f"  Qty MoM: {row.get('qty_mom','N/A')}",
        f"  Date: {row.get('stat_date','N/A')}",
    ]
    return "\n".join(lines)


def build_message(df: pd.DataFrame) -> str:
    if df.empty:
        return "No actionable signals today."
    header = "🔔 *GARCH-QUANT Korea Trade Signal Alert*\n"
    rows = [format_alert_row(r) for _, r in df.iterrows()]
    return header + "\n\n".join(rows) + "\n\n_Report generated automatically_"


def send_telegram(text: str, token: str = TG_BOT_TOKEN, chat_id: str = TG_CHAT_ID) -> bool:
    if not token or not chat_id:
        print("[alert_router] TG_BOT_TOKEN or TG_CHAT_ID not set — skipping Telegram")
        return False
    import urllib.request
    import urllib.parse
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    try:
        with urllib.request.urlopen(url, data, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[alert_router] Telegram send failed: {e}")
        return False


def route():
    if not SIGNAL_FILE.exists():
        print("[alert_router] signal_master.csv not found — skipping")
        return

    df = pd.read_csv(SIGNAL_FILE)
    df = df[df["signal_grade"].apply(lambda g: grade_priority(g) >= grade_priority("C"))]
    sent = send_telegram(build_message(df))
    print(f"[alert_router] Telegram sent={sent}")
    return sent


if __name__ == "__main__":
    route()
