-- Layer 2 — Observed Sources. Six views over Layer 1's atomic tables, three fragmented
-- "source systems" (billing_system, crm_system, marketing_system), each exposing a
-- deliberately imperfect slice of the truth. Design rationale + scenario mapping:
-- docs/02-stage-design-reports/layer2-observed-sources-design.md
--
-- This is what Stage 1 actually ingests. It never queries Layer 1's raw tables or
-- injected_events (held out) directly.
--
-- Apply:   psql "$DATABASE_URL" -f views.sql
-- Requires schema_layer2.sql (source_outages) to already be applied.

-- billing_system: daily, UTC day, exact revenue/orders/AOV. Purchase-based "active".
-- Total-gap-capable (a suppressed day has no row at all, not a zero).

CREATE OR REPLACE VIEW v_billing_daily_revenue AS
SELECT o.episode_id, o.day_offset,
       SUM(o.quantity * o.unit_price) AS revenue,
       COUNT(*) AS orders_count,
       ROUND(AVG(o.unit_price * o.quantity)::numeric, 2) AS avg_order_value
FROM orders o
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = o.episode_id AND so.source_name = 'billing_system'
      AND so.metric_name IS NULL
      AND o.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY o.episode_id, o.day_offset;

-- "active" = purchased in the trailing 30 days -- a genuine recency definition, so it's
-- actually comparable to crm's "interacted in trailing 30 days" (scenario 2), not just a
-- differently-named version of "still a customer of record."
CREATE OR REPLACE VIEW v_billing_active_customers AS
SELECT d.episode_id, d.day_offset,
       COUNT(DISTINCT o.customer_id) AS active_customers
FROM daily_state d
JOIN orders o ON o.episode_id = d.episode_id AND o.day_offset BETWEEN d.day_offset - 30 AND d.day_offset
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = d.episode_id AND so.source_name = 'billing_system'
      AND so.metric_name IS NULL
      AND d.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY d.episode_id, d.day_offset;

-- crm_system: weekly (ISO, Monday-start). "Active" = order OR ticket in trailing 30
-- days -- broader than billing's purchase-only definition (scenario 2). Synthetic
-- account-id mapping with injected duplicates/mismatches (scenario 6). Total-gap-capable
-- (a missed weekly snapshot).

CREATE OR REPLACE VIEW v_crm_weekly_active_customers AS
WITH weeks AS (
    SELECT DISTINCT e.episode_id,
           (date_trunc('week', e.start_date + d.day_offset * interval '1 day')::date - e.start_date) AS week_start_day_offset
    FROM episodes e
    JOIN daily_state d ON d.episode_id = e.episode_id
),
interactions AS (
    SELECT episode_id, customer_id, day_offset FROM orders
    UNION ALL
    SELECT episode_id, customer_id, day_offset FROM support_tickets
)
SELECT w.episode_id, w.week_start_day_offset,
       COUNT(DISTINCT i.customer_id) AS active_customers
FROM weeks w
JOIN interactions i
  ON i.episode_id = w.episode_id
 AND i.day_offset BETWEEN w.week_start_day_offset - 30 AND w.week_start_day_offset
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = w.episode_id AND so.source_name = 'crm_system'
      AND so.metric_name IS NULL
      AND w.week_start_day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY w.episode_id, w.week_start_day_offset;

CREATE OR REPLACE VIEW v_crm_customer_mapping AS
SELECT c.episode_id, c.customer_id,
    CASE WHEN mod(abs(hashtext(c.customer_id::text || ':mismatch')), 100) < 2
         THEN c.customer_id + 1  -- near-miss: silently mapped to the wrong customer
         ELSE c.customer_id
    END AS crm_account_id
FROM customers c
UNION ALL
-- unmerged duplicates: ~3% of customers also show up under a second synthetic account id
SELECT c.episode_id, c.customer_id, 900000 + c.customer_id AS crm_account_id
FROM customers c
WHERE mod(abs(hashtext(c.customer_id::text || ':dup')), 100) < 3;

-- marketing_system: billing-cycle month (30-day blocks starting day 15, not calendar
-- months -- scenario 5). attributed_revenue is a biased fraction of true revenue
-- (scenario 1) whose bias silently changes partway through the episode with no flag
-- (scenario 7). Partial-gap-capable (this metric alone can go dark).

CREATE OR REPLACE VIEW v_marketing_daily_attributed_revenue AS
SELECT o.episode_id, o.day_offset,
       ROUND((SUM(o.quantity * o.unit_price) *
             CASE WHEN o.day_offset < e.n_days / 2 THEN 0.87 ELSE 0.80 END)::numeric, 2) AS attributed_revenue
FROM orders o
JOIN episodes e ON e.episode_id = o.episode_id
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = o.episode_id AND so.source_name = 'marketing_system'
      AND (so.metric_name IS NULL OR so.metric_name = 'attributed_revenue')
      AND o.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY o.episode_id, o.day_offset, e.n_days;

-- Same "purchased in trailing 30 days" definition as billing -- this view exists purely
-- to demonstrate calendar misalignment (scenario 5) in isolation, not a second definitional
-- mismatch. Snapshotted at each billing-cycle block's last day, same pattern as the weekly
-- crm view snapshotting at each week's boundary.
CREATE OR REPLACE VIEW v_marketing_monthly_active_customers AS
WITH cycles AS (
    SELECT DISTINCT episode_id, floor((day_offset - 15) / 30.0)::int AS billing_cycle_index,
           MAX(day_offset) OVER (PARTITION BY episode_id, floor((day_offset - 15) / 30.0)::int) AS cycle_end_day
    FROM daily_state
    WHERE day_offset >= 15
)
SELECT c.episode_id, c.billing_cycle_index,
       COUNT(DISTINCT o.customer_id) AS active_customers
FROM cycles c
JOIN orders o ON o.episode_id = c.episode_id
             AND o.day_offset BETWEEN c.cycle_end_day - 30 AND c.cycle_end_day
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = c.episode_id AND so.source_name = 'marketing_system'
      AND so.metric_name IS NULL
      AND c.cycle_end_day BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY c.episode_id, c.billing_cycle_index;
