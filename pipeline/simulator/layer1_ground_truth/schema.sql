-- Layer 1 Ground Truth — Postgres schema (hosted on Neon; see .env.example at repo root).
-- Canonical DDL. Design rationale + ER diagram: docs/02-stage-design-reports/stage0-simulator-database-schema.md
--
-- Apply:   psql "$DATABASE_URL" -f schema.sql
-- Verify:  psql "$DATABASE_URL" -c '\dt'

BEGIN;

-- One row per simulated company/timeline.
CREATE TABLE IF NOT EXISTS episodes (
    episode_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    seed        INTEGER NOT NULL,
    n_days      INTEGER NOT NULL,
    start_date  DATE NOT NULL
);

-- Atomic entity. segment is our own dimension (RFM-style value tier — Olist customers are
-- individual consumers, not companies, so a B2B SMB/Enterprise split wouldn't fit the data);
-- region is an Olist-bootstrapped state code.
CREATE TABLE IF NOT EXISTS customers (
    customer_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id          INTEGER NOT NULL REFERENCES episodes(episode_id),
    segment              TEXT NOT NULL CHECK (segment IN ('New','Returning','VIP')),
    region               TEXT NOT NULL,
    signup_day_offset   INTEGER NOT NULL,
    churned_day_offset  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_customers_episode ON customers(episode_id);

-- Atomic entity. category/price bootstrapped from Olist's real catalog.
CREATE TABLE IF NOT EXISTS products (
    product_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id  INTEGER NOT NULL REFERENCES episodes(episode_id),
    category    TEXT NOT NULL,
    unit_cost   REAL NOT NULL,
    base_price  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_episode ON products(episode_id);

-- Latent driving variables with no natural atomic row of their own. One row per (episode, day).
CREATE TABLE IF NOT EXISTS daily_state (
    episode_id             INTEGER NOT NULL REFERENCES episodes(episode_id),
    day_offset             INTEGER NOT NULL,
    date                   DATE NOT NULL,
    marketing_spend        REAL NOT NULL,
    seasonality_factor     REAL NOT NULL,
    traffic                INTEGER NOT NULL,
    conversion_rate        REAL NOT NULL,
    product_reliability    REAL NOT NULL,
    satisfaction           REAL NOT NULL,
    competitor_activity    REAL NOT NULL,
    churn_rate             REAL NOT NULL,
    volatility_multiplier  REAL NOT NULL,
    PRIMARY KEY (episode_id, day_offset)
);

-- Atomic grain. revenue / orders_count / AOV are derived from this table, never stored.
CREATE TABLE IF NOT EXISTS orders (
    order_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id  INTEGER NOT NULL REFERENCES episodes(episode_id),
    day_offset  INTEGER NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    quantity    INTEGER NOT NULL,
    unit_price  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_episode_day ON orders(episode_id, day_offset);
CREATE INDEX IF NOT EXISTS idx_orders_customer    ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_product     ON orders(product_id);

-- Atomic grain. Feeds daily_state.satisfaction generation and Stage 6's evidence pipeline.
-- text is nullable: only the small Stage 6 demo corpus (seed_stage6_evidence.py) gets real
-- text, the existing 765K historical rows stay NULL, never retrofitted (see
-- .claude/plans/stage6-evidence-retrieval.md's Scope/Out).
CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id  INTEGER NOT NULL REFERENCES episodes(episode_id),
    day_offset  INTEGER NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    category    TEXT NOT NULL CHECK (category IN ('bug','shipping','billing','other')),
    text        TEXT
);
ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS text TEXT;
CREATE INDEX IF NOT EXISTS idx_tickets_episode_day ON support_tickets(episode_id, day_offset);

-- THE ANSWER KEY. Held out — the pipeline (Stage 1 onward) never queries this table;
-- it only exists for offline scoring. Zero, one, or several rows per episode
-- (multi-event episodes, reactive chaining via triggered_by_event_id).
CREATE TABLE IF NOT EXISTS injected_events (
    event_id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id               INTEGER NOT NULL REFERENCES episodes(episode_id),
    event_type               TEXT NOT NULL CHECK (event_type IN
                                ('product_outage','marketing_cut','competitor_launch','inventory_shortage')),
    severity                  TEXT NOT NULL CHECK (severity IN ('minor','moderate','severe')),
    onset_type                TEXT NOT NULL CHECK (onset_type IN ('step','ramp','spike_decay','delayed')),
    start_day_offset          INTEGER NOT NULL,
    end_day_offset            INTEGER,             -- NULL = still live / persists through episode end
    mitigation_day_offset     INTEGER,             -- NULL = never mitigated within the episode
    mitigation_completeness   REAL,                -- 0-1, NULL if no mitigation; <1 = lingering effect
    magnitude                 REAL NOT NULL,
    segment_multiplier        REAL NOT NULL DEFAULT 1.0,
    affected_segment          TEXT,                -- NULL = applies ~evenly, not concentrated
    affected_product_id       INTEGER REFERENCES products(product_id),  -- set only for inventory_shortage
    triggered_by_event_id     INTEGER REFERENCES injected_events(event_id),  -- reactive chaining; NULL = root cause
    description                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_episode ON injected_events(episode_id);

COMMIT;
