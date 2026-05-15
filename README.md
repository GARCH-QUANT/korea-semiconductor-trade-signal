# Korea Semiconductor Trade Signal

A reusable research and deployment skill for tracking Korean SSD/HBM export proxy signals.

## Core use cases

- KCS trade-statistics monitoring
- TRASS / KTSPI item-level HS research
- SSD / HBM proxy signal construction
- event study and excess-return research
- Telegram summaries and operational scheduling

## Main files

- `SKILL.md` — formal skill overview and usage guidance
- `src/korea_trade_tracker_pro.py` — core tracker (fetch → parse → signal → persist → alert)
- `sql/schema.sql` — SQLite database schema
- `sql/signal_queries.sql` — signal monitor view with MoM calculation
- `templates/pipeline_config.yaml` — pipeline configuration
- `ops/bootstrap_deploy.sh` — systemd deployment script

## Upload guidance

For skill uploads, include the whole folder so the structure, templates, and deployment guidance stay consistent.

See SKILL.md for full documentation.
