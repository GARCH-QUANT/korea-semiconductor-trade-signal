# Korea Semiconductor Trade Signal

> A full-lifecycle research and deployment framework that transforms Korean official trade statistics into actionable, verifiable semiconductor export proxy signals — SSD, DRAM, and HBM — with event studies, excess-return analysis, and Telegram alert delivery.

---

## Project Scope

This is **not** a simple data scraper or a static dashboard. It is a systematic research workflow built around Korean semiconductor export proxy signals, tracking changes in export value, volume, weight, and implied unit price, then mapping those changes into the equity event-study and excess-return research pipeline.

The core research indicator is the **implied export unit price**:

```
Implied Unit Price = Export Value ($) ÷ Export Volume (units)
                  or (when volume unavailable) Export Value ($) ÷ Export Weight (kg)
```

This is a proxy for average海关口径下的平均价格代理变量—not "precise厂商 ASP还原," but a high-frequency, continuous, comparable **directional signal**.

---

## Data Sources

| Source | URL | Role |
|--------|-----|------|
| **KCS** (Korea Customs Service) | customs.go.kr | Official trade statistics, weekly FX bulletins (USD/JPY/CNY/EUR) |
| **TRASS** (Korea Trade-Statistics Promotion Agency) | bandtrass.or.kr | Item-level trade statistics, HS code lookup, unit price analysis |

---

## SSD vs. HBM Research Discipline

### SSD (Solid-State Drives)
Start with the most well-defined primary HS code, then validate volume, value, and unit price口径. **Easiest to form the first actionable proxy signal system.**

### HBM (High-Bandwidth Memory)
HBM should **not** be treated as a single fixed code. The correct approach is to start with the DRAM / memory class as a pool entry point, then use the 10-digit sub-code pool for dynamic maintenance and iterative confirmation.

> HBM research难点是候选编码池管理、口径追踪和版本化维护—not chart rendering.

**SSD and HBM must be maintained, reported, and interpreted separately** to avoid mixed narratives that distort conclusions.

---

## System Architecture (6-Layer)

```
┌──────────────────────────────────────────────────────────┐
│  OUTPUT  │  Dashboard · Telegram Summary · MD Reports    │
├──────────────────────────────────────────────────────────┤
│  RESEARCH│  Event Study · Excess Return · Regression     │
├──────────────────────────────────────────────────────────┤
│  SIGNAL  │  Value · Volume · Weight · Price · Version   │
├──────────────────────────────────────────────────────────┤
│  SCRAPE  │  Request调度 · Site健康检查 · Anti-bot        │
├──────────────────────────────────────────────────────────┤
│  SOURCE  │  KCS (Customs) · TRASS (Trade Stats Agency) │
├──────────────────────────────────────────────────────────┤
│  OPS     │  Config · Cron · Archive · Failure Alert     │
└──────────────────────────────────────────────────────────┘
```

---

## Research Validation

Signals must move beyond "commodity signal" into "market signal." Map signals to:

- **Direct beneficiaries**: SK Hynix, Samsung, etc.
- **Ecosystem mapping**: AI servers, GPU supply chain, etc.

Observe return performance across different windows after signal publication. Use **excess returns** (not raw returns) as the primary metric to avoid confounding with broad market moves.

> Focus on: signal strength × exposure strength × excess return differentials across research buckets.

---

## Research Discipline

1. **Event timing alignment**: Korean signal publication time and tradable market hours do not align perfectly — always annotate timezone and window.
2. **Preliminary / Revised / Final分开**: Must be stored and interpreted separately; mixing them causes misjudgment.
3. **Version management**: Unit changes, weight unit changes, code rebucketing, and HBM candidate pool adjustments are noise sources —纳入版本管理.
4. **SSD / HBM分开维护**: Separate maintenance, reporting, and interpretation.

---

## Directory Structure

```
KoreaTradeSemiconductor/
├── README.md
├── SKILL.md                      # Skill formal documentation
├── config/
│   ├── hs_codes.yaml             # HS code pool (SSD primary + HBM candidates + version log)
│   └── hs_codes_explored.yaml
├── scripts/
│   ├── trass_fetcher.py          # TRASS item-level data fetcher
│   ├── trass_hs_search.py        # TRASS HS code search tool
│   ├── signals.py                # TRASS JSON → HS mapping → signal scoring (0 warnings)
│   ├── events.py                 # Event study framework
│   ├── report_generator.py       # Markdown signal report
│   ├── run_full_pipeline.py      # 4-stage pipeline orchestrator
│   └── tg_message_formatter.py   # Telegram push preview
├── src/
│   └── korea_trade_tracker_pro.py # Core tracker (fetch → parse → signal → persist → alert)
├── sql/
│   ├── schema.sql                # SQLite schema
│   └── signal_queries.sql       # Signal monitor view with MoM calculation
├── templates/
│   └── pipeline_config.yaml     # Pipeline configuration
├── ops/
│   └── bootstrap_deploy.sh      # Systemd deployment script
├── cron/
│   └── run_daily.sh.env
└── data/
    ├── raw/trass/               # TRASS JSON snapshots
    └── processed/               # Pipeline outputs
```

---

## Pipeline Stages

```
signals.py → events.py → report_generator.py → tg_message_formatter.py
```

| Script | Role | Output |
|--------|------|--------|
| `signals.py` | Extracts real HS codes from TRASS JSON top-level field, computes unit price MoM, grades signals A/B/C/Watch/Negative | `signal_master.csv` |
| `events.py` | Maps signals to tickers, merges returns, computes excess returns (1/3/5/10/20d) | `event_study_detail.csv`, `event_study_summary.csv` |
| `report_generator.py` | Generates Markdown research brief | `trade_signal_report.md` |
| `tg_message_formatter.py` | Formats Telegram push preview | `tg_message_preview.txt` |

---

## Current Status

✅ TRASS data fetching (Playwright + fn_receiver bypass)\
✅ HS code extraction from TRASS JSON (top-level `hs_code` field)\
✅ Signal scoring pipeline (0 warnings, 26 rows, 100% SSD mapping)\
✅ Full pipeline runnable (`run_full_pipeline.py`)\
🔄 Event study needs external returns data and ticker mapping\
🔄 HBM candidate pool needs further TRASS research

---

## Verified HS Codes (2026-01)

### SSD
| Code | Description | Level |
|------|-------------|-------|
| `852351` | Solid-state non-volatile storage | 6-digit ✅ |

### DRAM / HBM (no single fixed HBM code — use `854232` as pool entry point)
| Code | Description | Level |
|------|-------------|-------|
| `854232` | Memory IC (DRAM/HBM parent) | 6-digit ✅ |

---

## Disclaimer

All data originates from KCS (Korea Customs Service) and TRASS (Korea Trade-Statistics Promotion Agency) public information. For academic research and personal quantitative analysis only. HS code pools,口径 definitions, and research conclusions may contain errors — verify before citing.

---

*본 프로젝트는 학술 연구 및 개인 양적 분석을 목적으로 하며, 어떠한 투자 권유도 아닙니다.*
