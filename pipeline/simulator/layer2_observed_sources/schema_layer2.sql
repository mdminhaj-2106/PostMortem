-- Layer 2 support schema — source_outages, the one new table this layer needs.
-- Design rationale: docs/02-stage-design-reports/layer2-observed-sources-design.md §3
--
-- Apply:   psql "$DATABASE_URL" -f schema_layer2.sql
-- Requires Layer 1's schema.sql to already be applied (references episodes(episode_id)).

BEGIN;

CREATE TABLE IF NOT EXISTS source_outages (
    outage_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id         INTEGER NOT NULL REFERENCES episodes(episode_id),
    source_name         TEXT NOT NULL CHECK (source_name IN ('billing_system', 'crm_system', 'marketing_system')),
    metric_name          TEXT,  -- NULL = whole-source outage; otherwise the one metric suppressed (partial gap)
    start_day_offset     INTEGER NOT NULL,
    end_day_offset       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outages_episode_source ON source_outages(episode_id, source_name);

COMMIT;
