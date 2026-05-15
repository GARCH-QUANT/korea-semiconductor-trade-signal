-- Signal monitor view: joins latest price & qty, computes MoM

CREATE VIEW IF NOT EXISTS v_signal_monitor AS
WITH ranked AS (
    SELECT
        stat_period,
        item_group,
        hs_code,
        metric_type,
        value,
        unit,
        vintage_ts,
        is_final,
        ROW_NUMBER() OVER (
            PARTITION BY item_group, metric_type
            ORDER BY stat_period DESC, vintage_ts DESC
        ) AS rn
    FROM trade_series_clean
)
SELECT
    a.stat_period,
    a.item_group,
    a.hs_code,
    a.value          AS unit_price,
    a.vintage_ts     AS price_vintage,
    b.value          AS export_qty,
    b.vintage_ts     AS qty_vintage,
    (a.value / NULLIF(c.value, 0) - 1) AS unit_price_mom,
    (b.value / NULLIF(d.value, 0) - 1) AS qty_mom
FROM ranked a
LEFT JOIN ranked b
    ON a.item_group = b.item_group
   AND b.metric_type = 'export_qty_index'
   AND b.rn = 1
LEFT JOIN ranked c
    ON a.item_group = c.item_group
   AND c.metric_type = 'unit_price_index'
   AND c.stat_period < a.stat_period
   AND c.rn = 1
LEFT JOIN ranked d
    ON a.item_group = d.item_group
   AND d.metric_type = 'export_qty_index'
   AND d.stat_period < a.stat_period
   AND d.rn = 1
WHERE a.metric_type = 'unit_price_index'
  AND a.rn = 1;
