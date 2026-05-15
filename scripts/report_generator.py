from __future__ import annotations

from pathlib import Path
import pandas as pd

BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SIGNAL_FILE = OUTPUT_DIR / "signal_master.csv"
EVENT_SUMMARY_FILE = OUTPUT_DIR / "event_study_summary.csv"
EVENT_DETAIL_FILE  = OUTPUT_DIR / "event_study_detail.csv"
OUT_FILE  = OUTPUT_DIR / "trade_signal_report.md"


def load_inputs():
    signals = pd.read_csv(SIGNAL_FILE)         if SIGNAL_FILE.exists()         else pd.DataFrame()
    summary = pd.read_csv(EVENT_SUMMARY_FILE)   if EVENT_SUMMARY_FILE.exists()   else pd.DataFrame()
    detail  = pd.read_csv(EVENT_DETAIL_FILE)   if EVENT_DETAIL_FILE.exists()    else pd.DataFrame()
    return signals, summary, detail


def normalize(signals, summary, detail):
    if not signals.empty and "stat_date" in signals.columns:
        signals["stat_date"] = pd.to_datetime(signals["stat_date"], errors="coerce")
    return signals, summary, detail


def section_signal_overview(signals: pd.DataFrame) -> str:
    lines = ["## 信号概览", ""]
    if signals.empty:
        lines += ["当前暂无可用信号输出。", ""]
        return "\n".join(lines)

    latest_date = signals["stat_date"].dropna().max()
    latest = signals[signals["stat_date"] == latest_date].copy()
    latest = latest.sort_values(["signal_group", "signal_score"], ascending=[True, False])

    lines.append(f"- 最新信号日期：{latest_date.date()}")
    lines.append(f"- 最新样本数：{len(latest)}")
    if "signal_grade" in latest.columns:
        grade_counts = latest["signal_grade"].value_counts(dropna=False).to_dict()
        lines.append(f"- 最新分级分布：{grade_counts}")
    lines.append("")

    keep = [c for c in [
        "signal_group", "hs_code", "signal_type", "signal_score",
        "signal_grade", "price_qty_mom", "qty_mom", "value_mom",
    ] if c in latest.columns]
    if keep:
        lines.append(latest[keep].head(12).to_markdown(index=False))
        lines.append("")
    return "\n".join(lines)


def section_event_summary(summary: pd.DataFrame) -> str:
    lines = ["## 事件研究摘要", ""]
    if summary.empty:
        lines += ["当前暂无事件研究汇总结果。", ""]
        return "\n".join(lines)
    show = [c for c in [
        "group_type", "group_name", "count",
        "mean_excess_1d", "mean_excess_3d", "mean_excess_5d",
        "mean_excess_10d", "mean_excess_20d",
    ] if c in summary.columns]
    lines.append(summary[show].to_markdown(index=False))
    lines.append("")
    return "\n".join(lines)


def section_interpretation(signals: pd.DataFrame, summary: pd.DataFrame) -> str:
    lines = ["## 解释框架", ""]
    lines.append("- 若单价上升且数量同步走强，通常说明价格与出货共振，代理信号强度更高。")
    lines.append("- 若单价上升但数量显著下滑，则更可能反映结构变化、样本扰动或编码池变化。")
    lines.append("- 若 5 日到 20 日超额收益持续为正，则说明贸易代理信号可能具有可研究的市场解释力。")
    lines.append("- 对于 HBM，优先把它视为候选编码池研究对象，而不是单一固定编码。")
    if not signals.empty and "is_preliminary" in signals.columns:
        prelim_rate = signals["is_preliminary"].fillna(False).mean()
        lines.append(f"- 当前样本中暂定值占比约为 {prelim_rate:.1%}，正式结论需结合最终值复核。")
    lines.append("")
    return "\n".join(lines)


def section_next_steps(detail: pd.DataFrame) -> str:
    lines = ["## 后续动作", ""]
    lines.append("- 用真实股票收益与真实基准指数替换样例收益文件。")
    lines.append("- 加入事件时点对齐模块，避免韩国发布时间与各市场交易时点错位。")
    lines.append("- 将 SSD 与 HBM 分章输出，分别维护编码池和标的池。")
    lines.append("- 把版本字段、单位变化和候选码池变化纳入稳健性检验。")
    if not detail.empty and "ticker" in detail.columns:
        lines.append(
            f"- 当前事件研究已涉及 {detail['ticker'].nunique()} 个标的，"
            "可继续扩展直接受益层与生态映射层。"
        )
    lines.append("")
    return "\n".join(lines)


def build_report(signals, summary, detail) -> str:
    parts = [
        "# 韩国半导体贸易代理信号研究简报",
        "",
        "本简报基于韩国官方贸易统计与品目级贸易统计构建的 SSD / HBM 代理信号，",
        "目的是把贸易数据变化转化为可研究、可跟踪、可验证的市场信号。",
        "",
        section_signal_overview(signals),
        section_event_summary(summary),
        section_interpretation(signals, summary),
        section_next_steps(detail),
    ]
    return "\n".join(parts)


def run():
    signals, summary, detail = load_inputs()
    signals, summary, detail = normalize(signals, summary, detail)
    report = build_report(signals, summary, detail)
    OUT_FILE.write_text(report, encoding="utf-8")
    return OUT_FILE


if __name__ == "__main__":
    out = run()
    print(str(out))
