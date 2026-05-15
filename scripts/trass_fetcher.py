#!/usr/bin/env python3
"""
TRASS 品目贸易统计抓取脚本 v3
改进目标：稳定拉取连续月度数据，不依赖 BASE_MON='' 的隐式逻辑

核心改动（v2 → v3）：
  - 不再靠 BASE_MON='' 一次查全年，改为逐月独立请求（month=01..12）
  - 每月保存 raw JSON 快照，便于核查接口变化
  - 输出标准化 CSV 供 signals.py 使用

数据源：bandtrass.or.kr 기본조회（已验证）
验证状态：✅ fn_receiver + goSearch 方案可用（2026-01 实测）
"""

import json
import time
import yaml
import sys
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===================== 配置区 =====================
BASE_DIR       = Path(__file__).resolve().parent.parent
CONFIG_DIR     = BASE_DIR / "config"
CONFIG_FILE    = CONFIG_DIR / "hs_codes.yaml"
DATA_DIR       = BASE_DIR / "data"
RAW_DIR        = DATA_DIR / "raw" / "trass"
PROCESSED_DIR  = DATA_DIR / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ===================== 全局浏览器实例 =====================
BROWSER_INSTANCE = None
PLAYWRIGHT_PAGE  = None


# ===================== 核心浏览器交互 =====================

def get_playwright_page():
    """获取或创建全局 playwright page（复用浏览器 session）"""
    global BROWSER_INSTANCE, PLAYWRIGHT_PAGE
    if PLAYWRIGHT_PAGE is None:
        pw = sync_playwright().__enter__()
        BROWSER_INSTANCE = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        PLAYWRIGHT_PAGE  = BROWSER_INSTANCE.new_page()
        _init_page(PLAYWRIGHT_PAGE)
    return PLAYWRIGHT_PAGE


def _init_page(page):
    """初始化页面：加载主查询页 + 安装 fn_receiver"""
    page.goto(
        "https://www.bandtrass.or.kr/customs/total.do"
        "?command=CUS001View&viewCode=CUS00201",
        wait_until="domcontentloaded",
        timeout=30000
    )
    # 切换到品目/성질별 分类模式
    page.evaluate(
        "document.getElementById('GODS_TYPE').value='H';"
        "document.getElementById('GODS_TYPE').onchange();"
    )
    page.wait_for_timeout(500)
    # 安装 fn_receiver（填充 HS 编码字段）
    page.evaluate("""
        window.fn_receiver = function(obj) {
            if (!obj) return;
            jQuery('#FILTER1_CODE').html(obj.hs_cd || '');
            jQuery('#FILTER1_KOR').html(obj.qty_unit || '');
            jQuery('#FILTER1_GODS_UNIT').val(obj.unit || '10');
            document.getElementById('FILTER1_CODE_VALUE').value = obj.hs_cd || '';
            document.getElementById('FILTER1_KOR_VALUE').value = obj.qty_unit || '';
            document.getElementById('page').value = '1';
            jQuery('.paging').html('');
        };
    """)
    page.wait_for_timeout(200)


# ===================== 抓取：单编码 × 单月 =====================

def fetch_one_month(page, hs_code: str, year: int, month: int, trade_gb: str = "E") -> list[dict]:
    """
    用 Playwright 抓取单个 HS 编码 × 单个月份的贸易数据。

    逐月独立请求（不是 BASE_MON='' 查全年），确保 stat_date 连续可追踪。

    返回:
        list of dict: jqGrid 原始行数据，每行额外附加 BASE_YEAR / BASE_MON
    """
    unit = "4" if len(hs_code) == 4 else ("6" if len(hs_code) == 6 else "10")
    mon  = f"{month:02d}"

    # 填充 HS 编码字段
    page.evaluate(
        f"window.fn_receiver({{hs_cd:'{hs_code}', qty_unit:'', unit:'{unit}'}});"
    )
    page.wait_for_timeout(100)

    # 设置查询条件：明确指定月份（不是空字符串）
    page.evaluate(f"""
        document.getElementById('DATE_TYPE').value = 'M';
        document.getElementById('BASE_YEAR').value = '{year}';
        document.getElementById('BASE_MON').value = '{mon}';
        document.getElementById('EI_DITC').value = '{trade_gb}';
        document.getElementById('page').value = '1';
        jQuery('.paging').html('');
    """)
    page.wait_for_timeout(100)

    # 触发查询
    page.evaluate("goSearch();")
    page.wait_for_timeout(2000)

    # 读取行数据
    rows_json = page.evaluate("""
        (function() {
            try {
                var rows = $('#table_list_1').jqGrid('getRowData');
                return JSON.stringify(rows || []);
            } catch(e) {
                return JSON.stringify([{error: e.message}]);
            }
        })()
    """)
    rows = json.loads(rows_json)

    # 附加时间维度（每行显式标注年月，避免依赖 BASE_MON 解析）
    for row in rows:
        row["BASE_YEAR"] = str(year)
        row["BASE_MON"]  = mon

    return rows


def save_raw_snapshot(hs_code: str, year: int, month: int, raw_rows: list, fetched_at: str):
    """保存当月 raw JSON 快照"""
    ym = f"{year}{month:02d}"
    fp = RAW_DIR / f"trass_raw_{hs_code}_{ym}.json"
    fp.write_text(
        json.dumps({
            "hs_code":   hs_code,
            "year":      str(year),
            "month":     f"{month:02d}",
            "fetched_at": fetched_at,
            "row_count": len(raw_rows),
            "rows":      raw_rows,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return fp


# ===================== 抓取：单编码 × 全年12月 =====================

def fetch_year(hs_code: str, year: int, trade_gb: str = "E",
               months_arg: list = None) -> dict:
    """
    抓取单个 HS 编码全年 12 个月的数据。
    逐月独立请求，每月保存 raw 快照。
    """
    page = get_playwright_page()
    all_rows = []
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    months = months_arg if months_arg else [f"{m:02d}" for m in range(1, 13)]

    for month_str in months:
        month_int = int(month_str)
        try:
            rows = fetch_one_month(page, hs_code, year, month_int, trade_gb)
            # 每月独立落盘 raw
            save_raw_snapshot(hs_code, year, month_int, rows, fetched_at)
            all_rows.extend(rows)
            print(f"    {hs_code} {year}-{month_str}: {len(rows)} rows")
        except Exception as e:
            print(f"    {hs_code} {year}-{month_str}: ERROR {e}")
            save_raw_snapshot(hs_code, year, month_int, [{"error": str(e)}], fetched_at)

        time.sleep(1)

    return {
        "hs_code":    hs_code,
        "trade_type": trade_gb,
        "year":       str(year),
        "total_count": len(all_rows),
        "data":       all_rows,
        "fetched_at": fetched_at,
    }


# ===================== 批量查询 =====================

def fetch_multiple(hs_codes: list, year_from: int, year_to: int, export_only: bool = True,
                  months_arg: list = None):
    """
    批量查询多个 HS 编码，跨年份。
    复用同一个 playwright page，每年查满 12 个月。
    """
    results = []
    trade_gb = "E" if export_only else "I"
    label    = "출고(出口)" if export_only else "수입(进口)"

    for code in hs_codes:
        for year in range(year_from, year_to + 1):
            print(f"  → {code} {year} ({label})...")
            try:
                result = fetch_year(code, year, trade_gb, months_arg)
                results.append(result)
            except Exception as e:
                print(f"    ❌ 错误: {e}")
                results.append({"hs_code": code, "year": str(year), "error": str(e), "data": []})
    return results


# ===================== 数据解析与标准化 =====================

def parse_trade_data(raw_records: list) -> list[dict]:
    """
    将 TRASS jqGrid 原始行转为标准化 DataFrame 友好 dict。
    字段映射：
      Godds_CD   → HS_CODE
      GoddsNm    → HS_NAME
      TradeMny_C → TRADE_KRW（千韩元）
      MxWeight   → WEIGHT_KG
      Weight     → WEIGHT_KG（备用）
    """
    rows = []
    for rec in raw_records:
        rows.append({
            "HS_CODE":   rec.get("Godds_CD", ""),
            "HS_NAME":   rec.get("GoddsNm", ""),
            "BASE_YEAR": rec.get("BASE_YEAR", ""),
            "BASE_MON":  rec.get("BASE_MON", ""),
            # stat_date 统一格式：YYYY-MM-01
            "stat_date": f"{rec.get('BASE_YEAR', '')}-{rec.get('BASE_MON', '')}-01",
            # TRASS 实际字段名：EX_AMT（千韩元）、EX_WGHT（kg）
            "TRADE_KRW": float(rec.get("EX_AMT") or rec.get("TradeMny_C") or 0),
            "WEIGHT_KG": float(rec.get("EX_WGHT") or rec.get("MxWeight") or rec.get("Weight") or 0),
            # qty 在 TRASS 基本查询中通常为空，以 None 替代 0
            "EXPORT_QTY": None,
        })
    return rows


# ===================== 标准化 CSV 输出 =====================

def save_normalized_csv(all_results: list, year_from: int, year_to: int, export_only: bool):
    """将所有编码的原始数据解析并输出标准化 CSV 供 signals.py 使用"""
    import pandas as pd

    all_rows = []
    for result in all_results:
        parsed = parse_trade_data(result.get("data", []))
        for row in parsed:
            row["hs_code"]    = result["hs_code"]
            row["trade_type"] = result.get("trade_type", "")
            row["fetched_at"] = result.get("fetched_at", "")
        all_rows.extend(parsed)

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("  (无数据)")
        return None

    # 标准化列顺序
    cols = ["hs_code", "trade_type", "HS_CODE", "HS_NAME",
            "BASE_YEAR", "BASE_MON", "stat_date",
            "TRADE_KRW", "EXPORT_QTY", "WEIGHT_KG", "fetched_at"]
    df = df[[c for c in cols if c in df.columns]]

    out_path = PROCESSED_DIR / f"trass_monthly_panel_{year_from}_{year_to}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"\n  ✅ 标准化 CSV: {out_path}  ({len(df)} 行)")
    return out_path


# ===================== 配置文件读取 =====================

def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ===================== 主程序 =====================

def main():
    config = load_config()

    # 命令行参数
    year_from   = int(sys.argv[1]) if len(sys.argv) > 1 else (datetime.now().year - 1)
    year_to     = int(sys.argv[2]) if len(sys.argv) > 2 else year_from
    export_only = "--import" not in sys.argv

    # --codes 筛选（可选，如 --codes 852351 或 --codes 852351,854232）
    codes_arg = None
    for arg in sys.argv:
        if arg.startswith("--codes="):
            codes_arg = [c.strip() for c in arg.split("=", 1)[1].split(",")]
    # --months 筛选（可选，如 --months 01 02）
    months_arg = None
    try:
        mi = [i for i, a in enumerate(sys.argv) if a == "--months"]
        if mi:
            months_arg = sys.argv[mi[0] + 1 : sys.argv.index("--", mi[0]) if "--" in sys.argv[mi[0]:] else len(sys.argv)]
            months_arg = [m for m in months_arg if not m.startswith("--")]
    except Exception:
        months_arg = None

    trade_label = "출고(出口)" if export_only else "수입(进口)"
    print(f"\n{'='*60}")
    print(f"TRASS 韩国贸易统计数据抓取 v3")
    print(f"  年份: {year_from} ~ {year_to}")
    print(f"  类型: {trade_label}")
    print(f"  策略: 逐月独立请求（不依赖 BASE_MON=''）")
    print(f"{'='*60}\n")

    # 展开编码池（按 config 读，按 --codes 过滤）
    hs_pool = config  # 顶层即 ssd / hbm
    ssd_6   = [c["code"] for c in hs_pool.get("ssd", {}).get("primary_codes", [])    if c.get("code")]
    ssd_10  = [c["code"] for c in hs_pool.get("ssd", {}).get("ten_digit_codes", [])  if c.get("code")]
    dram_6  = [c["code"] for c in hs_pool.get("hbm", {}).get("candidate_6digit", []) if c.get("code")]
    dram_10 = [c["code"] for c in hs_pool.get("hbm", {}).get("candidate_10digit", []) if c.get("code")]

    all_ssd_codes  = [c for c in ssd_6 + ssd_10  if (codes_arg is None or c in codes_arg)]
    all_dram_codes = [c for c in dram_6 + dram_10 if (codes_arg is None or c in codes_arg)]
    all_results = []

    if all_ssd_codes:
        print(f"[SSD ({', '.join(all_ssd_codes)})]")
        results = fetch_multiple(all_ssd_codes, year_from, year_to, export_only, months_arg)
        all_results.extend(results)

    if all_dram_codes:
        print(f"\n[DRAM/HBM ({', '.join(all_dram_codes)})]")
        results = fetch_multiple(all_dram_codes, year_from, year_to, export_only, months_arg)
        all_results.extend(results)

    # 汇总保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = RAW_DIR / f"trass_raw_{year_from}_{year_to}_{'export' if export_only else 'import'}_{ts}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 原始 JSON: {raw_path}")

    # 输出标准化 CSV
    save_normalized_csv(all_results, year_from, year_to, export_only)

    # 打印摘要
    total_rows = sum(len(r.get("data", [])) for r in all_results)
    print(f"\n  总计: {len(all_results)} 个编码查询, 共 {total_rows} 条记录")

    # 关闭浏览器
    global PLAYWRIGHT_PAGE, BROWSER_INSTANCE
    if PLAYWRIGHT_PAGE:
        PLAYWRIGHT_PAGE.close()
    if BROWSER_INSTANCE:
        BROWSER_INSTANCE.close()
        PLAYWRIGHT_PAGE  = None
        BROWSER_INSTANCE = None


if __name__ == "__main__":
    main()
