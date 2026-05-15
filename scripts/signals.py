from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
RAW_DIR    = DATA_DIR / "raw" / "trass"
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = DATA_DIR / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_GLOB   = "trass_raw_*.json"
HS_CONFIG  = CONFIG_DIR / "hs_codes.yaml"


def load_hs_config(path=HS_CONFIG) -> pd.DataFrame:
    """读取 hs_codes.yaml，返回 signal_group / hs_code / code_status 映射表。"""
    if not path.exists():
        return pd.DataFrame(columns=["signal_group", "hs_code", "code_status", "code_pool_version"])

    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pool_version = cfg.get("version", "v1")
    rows = []

    # yaml 顶层是 ssd / hbm（不是 groups:）
    for group_key, group_block in cfg.items():
        if group_key in ("version", "version_history"):
            continue
        if not isinstance(group_block, dict):
            continue
        for key, status in [("primary_codes", "active"), ("ten_digit_codes", "active"),
                             ("candidate_6digit", "candidate"), ("candidate_10digit", "candidate")]:
            for item in group_block.get(key, []) or []:
                code = str(item.get("code", ""))
                if code:
                    rows.append({
                        "signal_group":      group_key.upper(),
                        "hs_code":           code,
                        "code_status":       status,
                        "code_pool_version": pool_version,
                    })
    return pd.DataFrame(rows)


def load_raw_trade_data(data_dir: Path = RAW_DIR, pattern: str = RAW_GLOB) -> pd.DataFrame:
    """
    Read TRASS v3 fetcher raw JSON snapshots.

    v3 produces two file types:
      - Single-code monthly snapshot: {hs_code, year, month, row_count, rows:[...]}
      - Multi-code merged file: [{hs_code, data:[...]}, ...]  (from earlier test runs)
    """
    rows = []
    for fp in sorted(data_dir.glob(pattern)):
        payload = json.loads(fp.read_text(encoding="utf-8"))

        if isinstance(payload, list):
            # Merged file: extract data field from each item
            for item in payload:
                records = item.get("data", []) if isinstance(item, dict) else []
                top_hs  = str(item.get("hs_code", "")) if isinstance(item, dict) else ""
                for rec in records:
                    if isinstance(rec, dict):
                        rec["raw_file"]     = fp.name
                        rec["_top_hs_code"] = top_hs
                        rows.append(rec)
        elif isinstance(payload, dict):
            # Single-code monthly snapshot: read rows directly
            records = payload.get("rows", [])
            top_hs  = str(payload.get("hs_code", ""))
            for rec in records:
                if isinstance(rec, dict):
                    rec["raw_file"]    = fp.name
                    rec["_top_hs_code"] = top_hs        # 顶层真实HS code注入row
                    rows.append(rec)
    return pd.DataFrame(rows)


def _find_col(df: pd.DataFrame, candidates: list[str], default=None):
    cmap = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in cmap:
            return cmap[name.lower()]
    return default


def normalize_trade_fields(df: pd.DataFrame) -> pd.DataFrame:
    """将 TRASS jqGrid 原始字段映射为标准化字段。"""
    if df.empty:
        return pd.DataFrame(columns=[
            "source", "stat_date", "period_type", "hs_code", "item_name",
            "export_value", "value_currency", "export_qty", "qty_unit",
            "export_weight", "weight_unit", "version_flag", "fetch_ts", "raw_file",
        ])

    out = df.copy()

    # TRASS 原始字段 → 标准字段
    rename_map = {
        "BASE_YEAR":  "base_year",
        "BASE_MON":   "base_month",
        "COL1":       "item_name_raw",   # HTML 格式化文本，先保留原样
        "EX_AMT":     "export_value",
        "IM_AMT":     "import_value",
        "EX_WGHT":    "export_weight",
        "IM_WGHT":    "import_weight",
        "Godds_CD":   "hs_code_raw",
        "GoddsNm":    "item_name_raw",
        "TradeMny_C": "export_value",
        "MxWeight":   "export_weight",
        "Weight":     "export_weight_alt",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})

    # 构造 stat_date（YYYY-MM-01）
    if "base_year" in out.columns and "base_month" in out.columns:
        out["stat_date"] = out.apply(
            lambda r: f"{r['base_year']}-{str(r['base_month']).zfill(2)}-01"
            if pd.notna(r.get("base_year")) else pd.NaT,
            axis=1,
        )
    out["stat_date"] = pd.to_datetime(out["stat_date"], errors="coerce")

    # 数值字段
    for c in ["export_value", "import_value", "export_weight", "export_weight_alt"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)

    # 合并重量（优先 EX_WGHT，备用 MxWeight）
    if "export_weight" in out.columns:
        out["weight_kg"] = out["export_weight"]
    elif "export_weight_alt" in out.columns:
        out["weight_kg"] = out["export_weight_alt"]
    else:
        out["weight_kg"] = 0.0

    # 补充字段
    out["source"]         = "TRASS"
    out["period_type"]    = "monthly"
    out["value_currency"] = "KRW"
    out["qty_unit"]       = None
    out["weight_unit"]    = "kg"
    out["version_flag"]    = "unknown"
    out["fetch_ts"]       = pd.Timestamp.now()
    # hs_code: 优先从顶层注入的 _top_hs_code 提取，其次从 COL1 HTML 里正则抽6位数字
    def _extract_hs_from_col1(col1_val):
        import re
        s = str(col1_val)
        m = re.search(r'\[(\d{6})\]', s)
        return m.group(1) if m else None

    if "_top_hs_code" in out.columns:
        out["hs_code"] = out["_top_hs_code"].astype(str).str.strip()
    elif "item_name_raw" in out.columns:
        out["hs_code"] = out["item_name_raw"].apply(_extract_hs_from_col1).fillna("UNKNOWN")
    else:
        out["hs_code"] = "UNKNOWN"
    out = out.drop(columns=["_top_hs_code"], errors="ignore")

    if "export_qty" not in out.columns:
        out["export_qty"] = pd.NA

    return out[[
        "source", "stat_date", "period_type", "hs_code", "item_name_raw",
        "export_value", "value_currency", "export_qty", "qty_unit",
        "export_weight", "weight_kg", "weight_unit",
        "version_flag", "fetch_ts", "raw_file",
    ]]


def attach_signal_group(df: pd.DataFrame, hs_cfg: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.assign(signal_group=None, code_status=None, code_pool_version=None)
    if hs_cfg.empty:
        return df.assign(signal_group="UNMAPPED", code_status="unknown", code_pool_version=None)
    merged = df.merge(hs_cfg, how="left", on="hs_code")
    merged["signal_group"]      = merged["signal_group"].fillna("UNMAPPED")
    merged["code_status"]       = merged["code_status"].fillna("unknown")
    merged["code_pool_version"] = merged["code_pool_version"].fillna("unknown")
    return merged


def compute_unit_price(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["unit_price_by_qty"]    = out["export_value"] / out["export_qty"].where(out["export_qty"] > 0)
    out["unit_price_by_weight"] = out["export_value"] / out["weight_kg"].where(out["weight_kg"] > 0)
    return out


def _pct(s: pd.Series) -> pd.Series:
    return s.replace(0, pd.NA).pct_change(fill_method=None)


def compute_changes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.sort_values(["signal_group", "hs_code", "stat_date"]).copy()
    grp = out.groupby(["signal_group", "hs_code"], dropna=False)

    out["value_mom"]       = grp["export_value"].transform(_pct)
    out["qty_mom"]         = grp["export_qty"].transform(_pct)
    out["weight_mom"]       = grp["weight_kg"].transform(_pct)
    out["price_qty_mom"]   = grp["unit_price_by_qty"].transform(_pct)
    out["price_weight_mom"] = grp["unit_price_by_weight"].transform(_pct)

    out["price_qty_rolling_3"] = grp["unit_price_by_qty"].transform(
        lambda s: s.rolling(3, min_periods=1).mean()
    )
    out["price_qty_rolling_6"] = grp["unit_price_by_qty"].transform(
        lambda s: s.rolling(6, min_periods=1).mean()
    )
    return out


def detect_metadata_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["signal_group", "hs_code", "stat_date"]).copy()
    grp = out.groupby(["signal_group", "hs_code"], dropna=False)

    out["prev_qty_unit"]    = grp["qty_unit"].shift(1)
    out["prev_weight_unit"] = grp["weight_unit"].shift(1)

    out["is_unit_changed"] = (
        ((out["qty_unit"] != out["prev_qty_unit"]) & out["prev_qty_unit"].notna())
        | ((out["weight_unit"] != out["prev_weight_unit"]) & out["prev_weight_unit"].notna())
    )
    out["is_preliminary"]    = out["version_flag"].astype(str).str.contains("prelim", case=False, na=False)
    out["is_code_rebucketed"] = out["code_status"].eq("candidate")
    out["revision_size"]      = pd.NA
    out["is_fx_sensitive"]    = out["value_currency"].ne("USD")
    return out.drop(columns=["prev_qty_unit", "prev_weight_unit"])


def score_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    px = out["price_qty_mom"].infer_objects(copy=False).fillna(out["price_weight_mom"])
    qx = out["qty_mom"].infer_objects(copy=False).fillna(out["weight_mom"])

    def classify(row):
        p   = px.loc[row.name]
        q   = qx.loc[row.name]
        pre = bool(row.get("is_preliminary", False))
        uc  = bool(row.get("is_unit_changed", False))
        rb  = bool(row.get("is_code_rebucketed", False))

        grade, stype, score = "Neutral", "mixed", 0

        if pd.notna(p) and pd.notna(q):
            if p > 0.08 and q >= 0:
                grade, stype, score = "A", "price_up_qty_up", 3
            elif p > 0.08 and q > -0.05:
                grade, stype, score = "B", "price_up_qty_soft", 2
            elif p > 0 and q < -0.05:
                grade, stype, score = "C", "price_up_qty_down", 1
            elif p < 0 and q < 0:
                grade, stype, score = "Negative", "price_down_qty_down", -2
            elif p < 0 and q >= 0:
                grade, stype, score = "Watch", "price_down_qty_up", -1

        if pre and grade in ("A", "B", "C"):
            grade_map = {"A": "B", "B": "C", "C": "Neutral"}
            grade = grade_map.get(grade, grade)
            score -= 1

        if uc or rb:
            stype += "_review"
        return pd.Series([stype, score, grade])

    tmp = out.apply(classify, axis=1)
    out["signal_type"]  = tmp[0].astype(object)
    out["signal_score"] = pd.to_numeric(tmp[1], errors="coerce").fillna(0).astype(float)
    out["signal_grade"] = tmp[2].astype(object)

    out["signal_id"] = (
        out["signal_group"].fillna("NA").astype(str) + "_"
        + out["hs_code"].fillna("NA").astype(str) + "_"
        + out["stat_date"].dt.strftime("%Y%m%d").fillna("nodate")
    )
    return out


def export_signal_tables(df: pd.DataFrame, out_dir: Path = OUTPUT_DIR) -> None:
    base_cols = [
        "signal_group", "hs_code", "stat_date", "period_type", "version_flag",
        "export_value", "value_currency", "export_qty", "qty_unit",
        "export_weight", "weight_unit", "source", "fetch_ts", "raw_file",
        "code_status", "code_pool_version",
    ]
    price_cols = [
        "signal_group", "hs_code", "stat_date",
        "unit_price_by_qty", "unit_price_by_weight",
        "value_mom", "qty_mom", "weight_mom",
        "price_qty_mom", "price_weight_mom",
        "price_qty_rolling_3", "price_qty_rolling_6",
        "version_flag",
    ]
    signal_cols = [
        "signal_id", "signal_group", "hs_code", "stat_date",
        "signal_type", "signal_score", "signal_grade",
        "price_qty_mom", "price_weight_mom", "qty_mom", "weight_mom", "value_mom",
        "version_flag", "is_unit_changed", "is_code_rebucketed",
        "is_preliminary", "revision_size", "is_fx_sensitive",
    ]

    df[[c for c in base_cols   if c in df.columns]].to_csv(
        out_dir / "normalized_trade_series.csv", index=False
    )
    df[[c for c in price_cols  if c in df.columns]].to_csv(
        out_dir / "unit_price_series.csv", index=False
    )
    df[[c for c in signal_cols if c in df.columns]].to_csv(
        out_dir / "signal_master.csv", index=False
    )


def run() -> pd.DataFrame:
    raw    = load_raw_trade_data()
    hs_cfg = load_hs_config()
    norm   = normalize_trade_fields(raw)
    mapped = attach_signal_group(norm, hs_cfg)
    priced = compute_unit_price(mapped)
    changed = compute_changes(priced)
    flagged = detect_metadata_flags(changed)
    scored  = score_signals(flagged)
    export_signal_tables(scored)
    return scored


if __name__ == "__main__":
    df = run()
    print(f"rows={len(df)}  output_dir={OUTPUT_DIR}")
