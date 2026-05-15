---
name: korea-semiconductor-trade-signal
version: 1.0.0
description: >
  Reusable research and deployment skill for tracking Korean SSD/HBM export proxy signals
  from KCS and TRASS, generating Telegram alerts, running event studies, and producing
  automated reports.
---

# Korea Semiconductor Trade Signal

Reusable framework for building a Korea semiconductor trade-signal research workflow based on:

- KCS official trade statistics portal and weekly customs exchange-rate disclosures
- TRASS / KTSPI item-level trade statistics, HS code lookup, customs exchange-rate lookup
- SSD / HBM proxy unit-price monitoring
- market mapping, event study, excess return analysis, and report generation
- operational deployment, alert routing, and snapshot archiving

## When to use

Use this skill when you want to:
- track Korean export proxy signals for SSD, DRAM, or HBM-related categories
- reverse engineer TRASS item-level query workflows
- build a monitoring dashboard and Telegram signal system
- connect trade proxy data with listed-equity event studies
- operationalize the workflow with scheduled execution and report snapshots

## Data sources

**KCS** (Korea Customs Service): Official trade statistics portal — publishes trade-statistics notices and weekly customs exchange-rate information.

**TRASS** (Korea Trade Statistics Promotion Institute): Designated domestic institution for trade-statistics preparation and delivery — offers item-level statistics, HS code search, customs exchange-rate lookup, and trade-statistics analysis.

## Package layout

- `src/`: core pipeline, research, signal, alert, and reporting scripts
- `sql/`: database schema and signal SQL views
- `templates/`: config, environment, input, and report templates
- `ops/`: deployment and scheduling templates, workflow notes, directory standards
- `research/`: reverse-engineering notes and watchlist guidance
- `examples/`: sample benchmark/return inputs and a local dashboard example

## Recommended workflow

1. Start with `research/trass_reverse_engineering_guide.md` and `src/korea_trade_tracker_pro.py`
2. Populate `templates/market_mapping_template.csv`, `templates/real_market_data_template.csv`, and `templates/market_calendar_template.csv`
3. Initialize the database using `sql/schema.sql` and `sql/signal_queries.sql`
4. Run `src/run_full_pipeline.py` for research generation
5. Use `src/tg_message_formatter.py` and `src/alert_router.py` for signal delivery
6. Use `src/archive_snapshot.py` to preserve report/data snapshots after each formal run

## Key entry points

- Tracker: `src/korea_trade_tracker_pro.py`
- Pipeline: `src/run_full_pipeline.py`
- Research summary: `src/generate_research_report.py`
- Dual SSD/HBM report: `src/generate_dual_section_report.py`
- Deployment: `ops/bootstrap_deploy.sh`

## Signal rules

| Level | Condition | Interpretation |
|-------|-----------|-----------------|
| A | unit_price_mom > 8% AND qty_mom >= -3% | Strong price signal, demand intact |
| B | unit_price_mom > 3% | Price watch |
| C | otherwise | No action |

## Notes

- Treat HBM as a maintained candidate-code pool rather than a single static code until you confirm the true 10-digit HSK mapping
- Distinguish quantity-based unit price from weight-based unit price
- Keep preliminary values, revised values, and final values versioned separately
- Separate SSD and HBM reporting logic to avoid mixed interpretation
- Credentials (TG_BOT_TOKEN, TG_CHAT_ID) must be set via environment variables — never hard-code
