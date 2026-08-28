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

-- Stage 4 (dimensional decomposition) sliced billing_system views. billing_system is
-- the one source already exact/ground-truth-equivalent for revenue and active_customers
-- (no second source has a region/segment/product breakdown to reconcile against -- see
-- .claude/plans/stage4-dimensional-decomposition.md), so these read the same way the
-- un-sliced billing views do, just grouped by one more real dimension column.
--
-- Every (day_offset, slice_value) pair is scaffolded explicitly (day source x real
-- distinct slice values, LEFT JOINed to orders, COALESCEd to 0) so a slice-day with no
-- orders reports revenue=0/active_customers=0 -- a real observation -- rather than a
-- missing row that would wrongly look like a data gap to Stage 2's eligibility gate.
-- The un-sliced views never needed this because "zero orders company-wide on a day"
-- essentially never happens at this dataset's scale; "zero orders for one small region
-- on a day" is common. Same whole-day billing outage suppression as the un-sliced views
-- -- there's no slice-level outage concept in Layer 1's schema.

CREATE OR REPLACE VIEW v_billing_daily_revenue_by_region AS
WITH regions AS (
    SELECT DISTINCT episode_id, region FROM customers
),
order_region AS (
    SELECT o.episode_id, o.day_offset, c.region, o.quantity, o.unit_price
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
)
SELECT d.episode_id, d.day_offset, r.region,
       COALESCE(SUM(orr.quantity * orr.unit_price), 0) AS revenue,
       COUNT(orr.region) AS orders_count
FROM daily_state d
JOIN regions r ON r.episode_id = d.episode_id
LEFT JOIN order_region orr
  ON orr.episode_id = d.episode_id AND orr.day_offset = d.day_offset AND orr.region = r.region
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = d.episode_id AND so.source_name = 'billing_system'
      AND so.metric_name IS NULL
      AND d.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY d.episode_id, d.day_offset, r.region;

CREATE OR REPLACE VIEW v_billing_daily_revenue_by_segment AS
WITH segments AS (
    SELECT DISTINCT episode_id, segment FROM customers
),
order_segment AS (
    SELECT o.episode_id, o.day_offset, c.segment, o.quantity, o.unit_price
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
)
SELECT d.episode_id, d.day_offset, s.segment,
       COALESCE(SUM(os.quantity * os.unit_price), 0) AS revenue,
       COUNT(os.segment) AS orders_count
FROM daily_state d
JOIN segments s ON s.episode_id = d.episode_id
LEFT JOIN order_segment os
  ON os.episode_id = d.episode_id AND os.day_offset = d.day_offset AND os.segment = s.segment
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = d.episode_id AND so.source_name = 'billing_system'
      AND so.metric_name IS NULL
      AND d.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY d.episode_id, d.day_offset, s.segment;

-- Keyed on products.category (the real Olist taxonomy, 4 distinct/episode) -- no
-- active_customers_by_product view exists: a customer isn't tied to one product, so
-- active_customers_purchased_30d only ever gets region/segment breakdowns
-- (dimension_config.py's DIMENSION_APPLICABILITY encodes this).
CREATE OR REPLACE VIEW v_billing_daily_revenue_by_product AS
WITH categories AS (
    SELECT DISTINCT episode_id, category FROM products
),
order_category AS (
    SELECT o.episode_id, o.day_offset, p.category, o.quantity, o.unit_price
    FROM orders o
    JOIN products p ON p.product_id = o.product_id
)
SELECT d.episode_id, d.day_offset, c.category,
       COALESCE(SUM(oc.quantity * oc.unit_price), 0) AS revenue,
       COUNT(oc.category) AS orders_count
FROM daily_state d
JOIN categories c ON c.episode_id = d.episode_id
LEFT JOIN order_category oc
  ON oc.episode_id = d.episode_id AND oc.day_offset = d.day_offset AND oc.category = c.category
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = d.episode_id AND so.source_name = 'billing_system'
      AND so.metric_name IS NULL
      AND d.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY d.episode_id, d.day_offset, c.category;

-- Same "purchased in trailing 30 days" definition as v_billing_active_customers, sliced.
CREATE OR REPLACE VIEW v_billing_active_customers_by_region AS
WITH regions AS (
    SELECT DISTINCT episode_id, region FROM customers
),
order_region AS (
    SELECT DISTINCT o.episode_id, o.day_offset, c.region, o.customer_id
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
)
SELECT d.episode_id, d.day_offset, r.region,
       COUNT(DISTINCT orr.customer_id) AS active_customers
FROM daily_state d
JOIN regions r ON r.episode_id = d.episode_id
LEFT JOIN order_region orr
  ON orr.episode_id = d.episode_id AND orr.region = r.region
  AND orr.day_offset BETWEEN d.day_offset - 30 AND d.day_offset
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = d.episode_id AND so.source_name = 'billing_system'
      AND so.metric_name IS NULL
      AND d.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY d.episode_id, d.day_offset, r.region;

CREATE OR REPLACE VIEW v_billing_active_customers_by_segment AS
WITH segments AS (
    SELECT DISTINCT episode_id, segment FROM customers
),
order_segment AS (
    SELECT DISTINCT o.episode_id, o.day_offset, c.segment, o.customer_id
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
)
SELECT d.episode_id, d.day_offset, s.segment,
       COUNT(DISTINCT os.customer_id) AS active_customers
FROM daily_state d
JOIN segments s ON s.episode_id = d.episode_id
LEFT JOIN order_segment os
  ON os.episode_id = d.episode_id AND os.segment = s.segment
  AND os.day_offset BETWEEN d.day_offset - 30 AND d.day_offset
WHERE NOT EXISTS (
    SELECT 1 FROM source_outages so
    WHERE so.episode_id = d.episode_id AND so.source_name = 'billing_system'
      AND so.metric_name IS NULL
      AND d.day_offset BETWEEN so.start_day_offset AND so.end_day_offset
)
GROUP BY d.episode_id, d.day_offset, s.segment;
