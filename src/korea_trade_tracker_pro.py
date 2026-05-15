#!/usr/bin/env python3
"""
Korea Semiconductor Trade Signal Tracker
KCS + TRASS data fetching, signal computation, SQLite persistence, Telegram alerts.
"""

import os, re, json, time, sqlite3, hashlib, logging
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR  = BASE_DIR / "data"
RAW_DIR   = DATA_DIR / "raw"
LOG_DIR   = BASE_DIR / "logs"
DB_PATH   = DATA_DIR / "trade_tracker.db"

for p in [DATA_DIR, RAW_DIR, LOG_DIR]:
    p.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "tracker_pro.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

KCS_URL       = "https://tradedata.go.kr/cts/index.do?menuId=ETS_MNU_00000105"
TRASS_INFO_URL = "http://m.trass.or.kr/m/newandroidjsp/sinfo.jsp?bAgent=web"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3, connect=3, read=3, backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def save_raw(source_name: str, body: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RAW_DIR / f"{source_name}_{ts}.html"
    path.write_text(body, encoding="utf-8")
    return str(path)


def log_health(source_name: str, source_url: str, ok: int,
               body: str, parsed: Dict[str, Any], err: Optional[str] = None):
    payload_path = save_raw(source_name, body) if body else None
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO source_health_log
               (source_name, source_url, checked_at, http_ok, page_hash, payload_path, parsed_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_name, source_url, utc_now(), ok,
             sha256_text(body) if body else None,
             payload_path,
             json.dumps({"parsed": parsed, "error": err}, ensure_ascii=False))
        )
        conn.commit()


def fetch_via_requests(session: requests.Session, url: str, timeout: int = 25) -> str:
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text


def fetch_via_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError(f"Playwright unavailable: {e}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()
        return html


def robust_fetch(source_name: str, url: str) -> str:
    session = create_session()
    last_err = None
    for method in ("requests", "playwright"):
        try:
            html = (fetch_via_requests(session, url) if method == "requests"
                    else fetch_via_playwright(url))
            logging.info("Fetch success %s via %s", source_name, method)
            return html
        except Exception as e:
            last_err = str(e)
            logging.warning("Fetch failed %s via %s: %s", source_name, method, e)
            time.sleep(1.5)
    raise RuntimeError(f"{source_name} fetch failed: {last_err}")


def parse_kcs(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    fx_match = re.search(r"USD\s*([0-9,]+\.?[0-9]*)", text)
    prelim = 1 if "잠정치" in text else 0
    return {
        "preliminary_hint": prelim,
        "usd_customs_fx": fx_match.group(1) if fx_match else None,
        "contains_notice": "공지사항" in text,
        "contains_press_release": "보도자료" in text,
        "sample": text[:300]
    }


def parse_trass(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    return {
        "has_item_stats": "품목별통계" in text or "품목별 통계" in text,
        "has_hs_search": "HS부호 검색" in text,
        "has_customs_fx": "관세 환율조회" in text,
        "service_operator": "한국무역통계진흥원" if "한국무역통계진흥원" in text else None,
        "sample": text[:300]
    }


def ensure_views(sql_dir: Path = BASE_DIR / "sql"):
    sql = (sql_dir / "signal_queries.sql").read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.executescript(sql)
        conn.commit()


def seed_demo_series():
    """Seed synthetic demo data. Replace with real KCS/TRASS ingestion in production."""
    rows = [
        ("2026-03-30", "SSD",       "8471704010", "unit_price_index", 1.16, "index", 0, 0),
        ("2026-04-30", "SSD",       "8471704010", "unit_price_index", 1.23, "index", 0, 0),
        ("2026-05-10", "SSD",       "8471704010", "unit_price_index", 1.35, "index", 0, 0),
        ("2026-03-30", "SSD",       "8471704010", "export_qty_index", 108.0, "index", 0, 0),
        ("2026-04-30", "SSD",       "8471704010", "export_qty_index", 114.0, "index", 0, 0),
        ("2026-05-10", "SSD",       "8471704010", "export_qty_index", 115.0, "index", 0, 0),
        ("2026-03-30", "HBM_PROXY", "854232xxxx", "unit_price_index", 1.22, "index", 0, 0),
        ("2026-04-30", "HBM_PROXY", "854232xxxx", "unit_price_index", 1.41, "index", 0, 0),
        ("2026-05-10", "HBM_PROXY", "854232xxxx", "unit_price_index", 1.61, "index", 0, 0),
        ("2026-03-30", "HBM_PROXY", "854232xxxx", "export_qty_index",  58.0, "index", 0, 0),
        ("2026-04-30", "HBM_PROXY", "854232xxxx", "export_qty_index",  64.0, "index", 0, 0),
        ("2026-05-10", "HBM_PROXY", "854232xxxx", "export_qty_index",  66.0, "index", 0, 0),
    ]
    with get_conn() as conn:
        for r in rows:
            conn.execute(
                """INSERT INTO trade_series_clean
                   (stat_period, item_group, hs_code, metric_type, value, unit, vintage_ts, is_final, anomaly_flag)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*r, utc_now())
            )
        conn.commit()


def compute_signals() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM v_signal_monitor ORDER BY item_group, stat_period"
        ).fetchall()
    events = []
    for r in rows:
        mom    = r["unit_price_mom"] or 0
        qty_mom = r["qty_mom"] or 0
        if mom > 0.08 and qty_mom >= -0.03:
            level, rule = "A", "price_up_gt_8_and_qty_not_weak"
        elif mom > 0.03:
            level, rule = "B", "price_up_watch"
        else:
            level, rule = "C", "no_action"
        events.append({
            "stat_period":   r["stat_period"],
            "item_group":    r["item_group"],
            "signal_level":  level,
            "trigger_rule":  rule,
            "signal_score":  round(mom * 100, 2),
            "message_text":  f"[{level}级] {r['item_group']} 单价环比 {mom:.1%} / 数量环比 {qty_mom:.1%} / 期别 {r['stat_period']}"
        })
    return events


def persist_events(events: List[Dict[str, Any]]):
    with get_conn() as conn:
        for e in events:
            conn.execute(
                """INSERT INTO signal_event
                   (stat_period, item_group, signal_level, trigger_rule, signal_score, message_text, telegram_sent_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (e["stat_period"], e["item_group"], e["signal_level"],
                 e["trigger_rule"], e["signal_score"], e["message_text"], None)
            )
        conn.commit()


def send_telegram(text: str):
    token   = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20
    ).raise_for_status()


def main():
    session = create_session()

    for source_name, url, parser in [
        ("KCS",   KCS_URL,        parse_kcs),
        ("TRASS", TRASS_INFO_URL, parse_trass)
    ]:
        try:
            html    = robust_fetch(source_name, url)
            parsed  = parser(html)
            log_health(source_name, url, 1, html, parsed)
        except Exception as e:
            log_health(source_name, url, 0, "", {}, str(e))

    ensure_views()
    seed_demo_series()
    events = compute_signals()
    persist_events(events)

    for e in events:
        if e["signal_level"] in {"A", "B"}:
            try:
                send_telegram(e["message_text"])
            except Exception as ex:
                logging.warning("telegram send failed: %s", ex)

    print(json.dumps({"events": events[:10]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
