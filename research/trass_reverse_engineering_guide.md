# TRASS Reverse-Engineering Guide

> How to fetch item-level Korean trade statistics from TRASS (bandtrass.or.kr) when the official API is not publicly documented. Covers the Playwright bypass technique, `fn_receiver` callback trick, and the JSON snapshot format used by the pipeline.

---

## Background

TRASS (한국무역통계진흥원, Korea Trade Statistics Promotion Institute) publishes item-level trade statistics at [bandtrass.or.kr](https://bandtrass.or.kr). The public UI requires JavaScript rendering to query data — a blocking API is not documented. This guide documents the workaround used in `trass_fetcher.py`.

---

## Overall Approach

1. Use **Playwright** (Chromium headless) to open the query page
2. Inject a `window.fn_receiver` callback that captures JSON responses
3. Trigger the query via the page's JS bridge
4. Capture the JSON payload before it gets HTML-formatted and rendered into the grid
5. Write the raw JSON snapshot to `data/raw/trass/`

---

## `fn_receiver` Trick

TRASS's internal JS makes XHR/fetch calls to its backend. Instead of intercepting via `route`/`handle`, inject a global callback:

```javascript
window.fn_receiver = function(payload) {
    window.__captured = payload;
};
```

After the query, read `window.__captured` via `page.evaluate()`.

---

## Key URL Patterns

| Purpose | URL |
|---------|-----|
| Item-level query page | `https://bandtrass.or.kr/ktrass/stat/expectsea/search.do` |
| HS code search | `https://bandtrass.or.kr/ktrass/code/hs/search.do` |

---

## Query Parameters (known)

```
hs_cd         — 6-digit or 10-digit HS code
ex_imp_cls    — export (1) or import (2)
mon_cyc       — monthly (1) or quarterly (2)
bef_aft       — cumulative (1) or monthly (2)
inq_obj_val   — USD (1) or KRW (2)
```

---

## Pipeline Integration

```
trass_fetcher.py        →  fetches and writes raw JSON snapshots
signals.py              →  reads snapshots, extracts hs_code from JSON top-level field
report_generator.py     →  produces the research brief
```

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Empty `rows` array | Query returned 0 records for that HS/month | Verify HS code is valid for the period |
| HTML in `COL1` field | TRASS returned formatted grid HTML | Ensure `fn_receiver` captures the raw JSON before HTML rendering |
| `BASE_MON` null | `bef_aft=1` cumulative mode returns annual totals | Use `bef_aft=2` for monthly breakdown |
| Playwright timeout | Site changed its JS or blocked the headless session | Rotate user-agent, add delays, check site health |

---

## TRASS Data Format (v3 JSON Snapshot)

```json
{
  "hs_code": "852351",
  "year": "2024",
  "month": "01",
  "fetched_at": "2026-05-16T03:49:54",
  "row_count": 1,
  "rows": [
    {
      "NUM": "1",
      "COL1": "<font style=\"color:#337ab7;cursor:pointer;\">[852351] 솔리드 스테이트...</font>",
      "EX_AMT": "501798372",
      "EX_WGHT": "157522.18",
      "BASE_YEAR": "2024",
      "BASE_MON": "01"
    }
  ]
}
```

> **Note:** `COL1` contains HTML-formatted text with the real HS code in brackets `[852351]`. The top-level `hs_code` field is the canonical value — use it instead of parsing HTML.

---

## HS Code Verification (2026-01)

| Code | Description | Level |
|------|-------------|-------|
| `852351` | SSD (solid-state non-volatile storage) | 6-digit ✅ |
| `854232` | DRAM/HBM parent code — use as pool entry point | 6-digit ✅ |
| `8542321030` | Specific memory IC sub-code | 10-digit ✅ |

---

## Further Research

- Confirm whether TRASS publishes 10-digit breakdowns for HBM specifically
- Monitor TRASS for changes in HS code classification that could affect continuity
- Cross-check TRASS unit-price against KCS weekly FX bulletin values
