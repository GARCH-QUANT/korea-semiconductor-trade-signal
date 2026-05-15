from __future__ import annotations

from pathlib import Path
import pandas as pd

BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SIGNAL_FILE  = OUTPUT_DIR / "signal_master.csv"
SUMMARY_FILE = OUTPUT_DIR / "event_study_summary.csv"
REPORT_FILE  = OUTPUT_DIR / "trade_signal_report.md"
OUT_FILE    = OUTPUT_DIR / "tg_message_preview.txt"


def load_inputs():
    signals = pd.read_csv(SIGNAL_FILE)  if SIGNAL_FILE.exists()  else pd.DataFrame()
    summary = pd.read_csv(SUMMARY_FILE) if SUMMARY_FILE.exists() else pd.DataFrame()
    report = REPORT_FILE.read_text(encoding="utf-8") if REPORT_FILE.exists() else ""
    return signals, summary, report


def normalize(signals: pd.DataFrame, summary: pd.DataFrame):
    if not signals.empty and "stat_date" in signals.columns:
        signals["stat_date"] = pd.to_datetime(signals["stat_date"], errors="coerce")
    return signals, summary


def latest_signal_block(signals: pd.DataFrame) -> list[str]:
    lines = ["【最新贸易代理信号】"]
    if signals.empty:
        lines.append("- 当前暂无可用信号。")
        return lines

    latest_date = signals["stat_date"].dropna().max()
    latest = signals[signals["stat_date"] == latest_date].copy()
    latest = latest.sort_values("signal_score", ascending=False)

    lines.append(f"- 日期：{latest_date.date()}")
    lines.append(f"- 样本数：{len(latest)}")
    if "signal_grade" in latest.columns:
        lines.append(f"- 分级分布：{latest['signal_grade'].value_counts(dropna=False).to_dict()}")

    for _, row in latest.head(5).iterrows():
        lines.append(
            f"- {row.get('signal_group','?')} | {row.get('hs_code','?')} | "
            f"{row.get('signal_grade','?')} | score={row.get('signal_score','?')} | "
            f"type={row.get('signal_type','?')}"
        )
    return lines


def event_summary_block(summary: pd.DataFrame) -> list[str]:
    lines = ["", "【事件研究摘要】"]
    if summary.empty:
        lines.append("- 当前暂无事件研究汇总。")
        return lines

    preferred = (
        summary[summary["group_type"].isin(["signal_group", "signal_grade"])].copy()
        if "group_type" in summary.columns else summary.copy()
    )
    for _, row in preferred.head(6).iterrows():
        lines.append(
            f"- {row.get('group_type','?')} / {row.get('group_name','?')} / "
            f"n={row.get('count','?')} / "
            f"excess_5d={row.get('mean_excess_5d','?')} / "
            f"excess_10d={row.get('mean_excess_10d','?')}"
        )
    return lines


def interpretation_block(signals: pd.DataFrame, summary: pd.DataFrame) -> list[str]:
    lines = ["", "【简要判断】"]
    if signals.empty:
        lines.append("- 当前无法形成研究判断。")
        return lines

    top = signals.sort_values("signal_score", ascending=False).head(1)
    if not top.empty:
        row = top.iloc[0]
        lines.append(
            f"- 当前最强信号来自 {row.get('signal_group','?')}，"
            f"等级 {row.get('signal_grade','?')}，类型 {row.get('signal_type','?')}。"
        )
    lines.append("- 单价上升且数量不弱时，通常强于单价上升但数量明显走弱的情形。")
    lines.append("- HBM 相关结果建议继续结合候选编码池与版本状态复核。")
    return lines


def footer_block() -> list[str]:
    return [
        "",
        "【说明】",
        "- 本摘要基于韩国官方贸易统计与 TRASS 品目统计代理信号生成。",
        "- TRASS 由韩国贸易统计推广院（KTSPI）运营。",
        "- KCS 页面公开官方贸易统计入口，并发布每周关税汇率信息。",
    ]


def build_message(signals: pd.DataFrame, summary: pd.DataFrame, report: str) -> str:
    blocks = []
    blocks.extend(latest_signal_block(signals))
    blocks.extend(event_summary_block(summary))
    blocks.extend(interpretation_block(signals, summary))
    blocks.extend(footer_block())
    msg = "\n".join(blocks)
    if len(msg) > 3500:
        msg = msg[:3500] + "\n..."
    return msg


def run():
    signals, summary, report = load_inputs()
    signals, summary = normalize(signals, summary)
    msg = build_message(signals, summary, report)
    OUT_FILE.write_text(msg, encoding="utf-8")
    return OUT_FILE


if __name__ == "__main__":
    out = run()
    print(str(out))
