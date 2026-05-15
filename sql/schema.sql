-- Korea Semiconductor Trade Signal — SQLite Schema

CREATE TABLE IF NOT EXISTS source_health_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name  TEXT NOT NULL,
    source_url   TEXT NOT NULL,
    checked_at   TEXT NOT NULL,
    http_ok      INTEGER NOT NULL,
    page_hash    TEXT,
    payload_path TEXT,
    parsed_summary TEXT
);

CREATE TABLE IF NOT EXISTS trade_series_clean (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_period    TEXT NOT NULL,
    item_group     TEXT NOT NULL,
    hs_code        TEXT NOT NULL,
    metric_type    TEXT NOT NULL,
    value          REAL NOT NULL,
    unit           TEXT NOT NULL,
    vintage_ts     TEXT NOT NULL,
    is_final       INTEGER NOT NULL DEFAULT 0,
    anomaly_flag   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS signal_event (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_period     TEXT NOT NULL,
    item_group      TEXT NOT NULL,
    signal_level    TEXT NOT NULL,
    trigger_rule    TEXT NOT NULL,
    signal_score    REAL NOT NULL,
    message_text    TEXT NOT NULL,
    telegram_sent_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_series_period_item
    ON trade_series_clean(stat_period, item_group, metric_type);

CREATE INDEX IF NOT EXISTS idx_signal_level
    ON signal_event(signal_level, stat_period);
