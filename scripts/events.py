from __future__ import annotations

from pathlib import Path
import pandas as pd

BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SIGNAL_FILE = OUTPUT_DIR / "signal_master.csv"
RETURNS_FILE = DATA_DIR / "sample_returns_multiwindow.csv"
BENCH_FILE   = DATA_DIR / "sample_benchmark_returns.csv"
MAPPING_FILE = DATA_DIR / "market_mapping_template.csv"


def load_inputs(
    signal_file: Path = SIGNAL_FILE,
    returns_file: Path = RETURNS_FILE,
    bench_file:  Path = BENCH_FILE,
    mapping_file: Path = MAPPING_FILE,
):
    signals = pd.read_csv(signal_file)   if signal_file.exists()   else pd.DataFrame()
    returns = pd.read_csv(returns_file)   if returns_file.exists()  else pd.DataFrame()
    bench   = pd.read_csv(bench_file)    if bench_file.exists()    else pd.DataFrame()
    mapping = pd.read_csv(mapping_file)  if mapping_file.exists()  else pd.DataFrame()
    return signals, returns, bench, mapping


def normalize_inputs(signals, returns, bench, mapping):
    if not signals.empty and "stat_date" in signals.columns:
        signals["stat_date"] = pd.to_datetime(signals["stat_date"], errors="coerce")
    if not returns.empty and "event_date" in returns.columns:
        returns["event_date"] = pd.to_datetime(returns["event_date"], errors="coerce")
    if not bench.empty and "event_date" in bench.columns:
        bench["event_date"] = pd.to_datetime(bench["event_date"], errors="coerce")
    for c in ["signal_group", "ticker", "exposure_type", "market"]:
        if c not in mapping.columns:
            mapping[c] = None
    return signals, returns, bench, mapping


def filter_researchable_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return signals
    out = signals.copy()
    out = out[~out["signal_grade"].isin(["Neutral"])]
    if "is_unit_changed" in out.columns:
        out = out[~out["is_unit_changed"].fillna(False)]
    if "is_code_rebucketed" in out.columns:
        out = out[~out["is_code_rebucketed"].fillna(False)]
    return out


def map_signals_to_tickers(signals: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    if signals.empty or mapping.empty:
        return pd.DataFrame(columns=[
            "signal_id", "signal_group", "stat_date", "ticker", "exposure_type", "market",
        ])
    cols = ["signal_id", "signal_group", "stat_date", "signal_grade", "signal_score", "signal_type"]
    merged = signals[cols].merge(
        mapping[["signal_group", "ticker", "exposure_type", "market"]],
        on="signal_group", how="left",
    )
    return merged


def merge_returns(mapped: pd.DataFrame, returns: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    if mapped.empty:
        return mapped
    out = mapped.merge(
        returns,
        left_on=["ticker", "stat_date"],
        right_on=["ticker", "event_date"],
        how="left",
    )
    if not bench.empty:
        out = out.merge(
            bench,
            left_on=["market", "stat_date"],
            right_on=["market", "event_date"],
            how="left",
            suffixes=("", "_bench"),
        )
    return out


def compute_excess_returns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in [1, 3, 5, 10, 20]:
        rcol = f"fwd_{w}d_return"
        bcol = f"bench_{w}d_return"
        ecol = f"excess_{w}d_return"
        if rcol not in out.columns:
            out[rcol] = pd.NA
        if bcol not in out.columns:
            out[bcol] = pd.NA
        out[ecol] = pd.to_numeric(out[rcol], errors="coerce") - pd.to_numeric(out[bcol], errors="coerce")
    return out


def build_event_detail(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "signal_id", "signal_group", "stat_date", "ticker", "market", "exposure_type",
        "signal_grade", "signal_score", "signal_type",
        "fwd_1d_return", "fwd_3d_return", "fwd_5d_return", "fwd_10d_return", "fwd_20d_return",
        "excess_1d_return", "excess_3d_return", "excess_5d_return",
        "excess_10d_return", "excess_20d_return",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()


def build_event_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(columns=[
            "group_type", "group_name", "count",
            "mean_excess_1d", "mean_excess_3d", "mean_excess_5d",
            "mean_excess_10d", "mean_excess_20d",
        ])
    rows = []
    for group_type, key in [
        ("signal_group", "signal_group"),
        ("exposure_type", "exposure_type"),
        ("signal_grade", "signal_grade"),
    ]:
        tmp = (
            detail.groupby(key, dropna=False)
            .agg(
                count=("ticker", "count"),
                mean_excess_1d=("excess_1d_return", "mean"),
                mean_excess_3d=("excess_3d_return", "mean"),
                mean_excess_5d=("excess_5d_return", "mean"),
                mean_excess_10d=("excess_10d_return", "mean"),
                mean_excess_20d=("excess_20d_return", "mean"),
            )
            .reset_index()
            .rename(columns={key: "group_name"})
        )
        tmp.insert(0, "group_type", group_type)
        rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


def export_outputs(detail: pd.DataFrame, summary: pd.DataFrame, out_dir: Path = OUTPUT_DIR) -> None:
    detail.to_csv(out_dir / "event_study_detail.csv",  index=False)
    summary.to_csv(out_dir / "event_study_summary.csv", index=False)


def run():
    signals, returns, bench, mapping = load_inputs()
    signals, returns, bench, mapping = normalize_inputs(signals, returns, bench, mapping)
    signals = filter_researchable_signals(signals)
    mapped  = map_signals_to_tickers(signals, mapping)
    merged  = merge_returns(mapped, returns, bench)
    merged  = compute_excess_returns(merged)
    detail  = build_event_detail(merged)
    summary = build_event_summary(detail)
    export_outputs(detail, summary)
    return detail, summary


if __name__ == "__main__":
    detail, summary = run()
    print(f"detail_rows={len(detail)}  summary_rows={len(summary)}  output_dir={OUTPUT_DIR}")
