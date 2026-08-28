# Simulator — Layer 1 Ground Truth — Design Report

**Status:** Design complete, pre-implementation. Blocks every other stage — nothing downstream has data to run against until this exists.

---

## 1. Unit of generation: the episode

Per the architecture report, Component A/B training needs "several hundred episodes," each independently labeled and stratifiable into train/val/test. So the generator's output unit is an **episode**, not one long continuous timeline:

- Each episode is a fresh fake business: its own customers, products, day-zero baselines.
- Each episode spans `n_days` (default 120: enough runway for a delayed/ramping cause like product-outage churn to fully show up, plus pre/post buffer).
- Each episode gets **exactly one** injected event, placed at a randomized day offset (not day 0, not the last day — needs both pre- and post-event history), **or no event at all** (pure-noise episode — the negative control for "ability to decline").
- Event type, magnitude, and affected segment/product are randomized per episode within declared ranges, so training data covers a spread, not one canned shape per cause.

Target: ~400 episodes, roughly balanced across the 5 outcomes (4 event types + noise) — stratified split happens downstream at training time, not here.

## 2. Tables (SQLite)

Atomic-grain only. KPIs (revenue, orders count, AOV, active customers, complaint rate) are **not stored** — they're aggregates computed at Layer 2 view time, so nothing can drift out of sync with the atomic rows that actually happened. This mirrors Stage 1's own "one atomic truth, bucket on demand" principle instead of fighting it.

```
episodes
  episode_id, seed, n_days, start_date

customers
  customer_id, episode_id, segment, region, signup_day_offset, churned_day_offset (nullable)

products
  product_id, episode_id, category, unit_cost, base_price

daily_state                      -- latent driving variables, no natural atomic row
  episode_id, day_offset, date,
  marketing_spend, seasonality_factor, traffic,
  conversion_rate, product_reliability,
  satisfaction, competitor_activity, churn_rate

orders                           -- atomic; revenue/AOV/orders-count derive from this
  order_id, episode_id, day_offset, customer_id, product_id, quantity, unit_price

support_tickets                  -- atomic; complaint-rate KPI derives from this
  ticket_id, episode_id, day_offset, customer_id, category

injected_events                  -- ground truth. Held out — never fed to the pipeline as input.
  event_id, episode_id, event_type, start_day_offset, end_day_offset,
  magnitude, affected_segment (nullable), affected_product_id (nullable), description
```

`active_customers(t)` = count of customers where `signup_day_offset <= t` and (`churned_day_offset` is null or `> t`) — derived, not stored. `revenue(t)` = `sum(quantity * unit_price)` for that day's orders — also derived.

## 3. Generation order (per episode, per day)

Structural equations, in dependency order — each day's state feeds the next day where there's momentum (churn, active-customer base):

1. `seasonality_factor` — deterministic function of day-of-week + day-of-year (weekend dip, a mild yearly wave). No randomness here; it's the thing Stage 2 must learn to *not* mistake for a real signal.
2. `marketing_spend` = baseline + noise (event: **marketing_cut** drops this by `magnitude` as a step function at `start_day_offset`, persists).
3. `product_reliability` = baseline near 1.0 + noise (event: **product_outage** drops this sharply at onset, ramps back to baseline by `end_day_offset`).
4. `competitor_activity` = baseline + noise (event: **competitor_launch** steps this up at onset, decays slowly — not a hard cutoff).
5. `traffic` = `f(marketing_spend, seasonality_factor, noise)`.
6. `conversion_rate` = `f(pricing=baseline, product_reliability, noise)`.
7. Sample `orders_count ≈ traffic × conversion_rate` (Poisson draw around that expected count), then generate that many `orders` rows: pick `customer_id` (existing active customer or new signup), `product_id` (event: **inventory_shortage** zeroes out sampling weight for `affected_product_id` during its window), `quantity`, `unit_price` (small noise around `base_price`).
8. Sample `support_tickets` count as `f(product_reliability, noise)`, generate that many rows with `customer_id`.
9. `satisfaction` = `f(support_complaints_count, noise)`.
10. `churn_rate` = `f(satisfaction, competitor_activity, noise)`, with **competitor_launch**'s effect weighted higher for customers in `affected_segment` (segment-concentrated churn, not broad-based). Apply as a per-customer Bernoulli draw among active customers → set `churned_day_offset` for the ones who churn that day.
11. **product_outage**'s churn effect is delayed/ramping: `churn_rate` bump is a function of *cumulative* complaints since onset, not a same-day step — this is what gives it the "delayed, ramping onset" fingerprint the architecture report calls for, distinct from marketing_cut's "immediate, broad-based" one.

**Pure-noise episodes** skip step 2–4's event branches entirely — every variable is just baseline + noise, no injected effect anywhere. This is the actual mechanism behind "ability to decline": the label is `event_type = null`, and nothing about that day's generation differs mechanically from a quiet week in an event episode.

## 4. Open parameters (need a value, not a design decision — pick defaults and move on)

- `n_days` = 120, ~400 episodes, ~5 customers/day baseline signup rate, 2–4 products/episode, 2 segments (SMB/Enterprise) × 2–3 regions — all easy to tune after the first end-to-end run once Stage 2/Component A actually trains on it.
- Noise magnitudes and event `magnitude` ranges: start with something visibly detectable (event effect ≫ noise std), tighten later if the classifier scores too easily.

## 5. Explicitly out of scope for Layer 1

- CRM notes / review text — templated text generation belongs with Stage 6 (evidence pipeline); Layer 1 only needs to emit the *numeric* KPI substrate first.
- Olist hybrid enrichment — optional polish, not before the synthetic path works end to end.
- Pricing-change and seasonal/regional-economic cause categories (PRD's fuller cause list) — the architecture report's scope guard already caps this at the 4 injected events + noise; the other cause labels in Component B's label space stay unimplemented for the prototype.

## 6. What this hands to Layer 2

Layer 2's SQL views read these 7 tables directly and are responsible for all the degradation (grain, cadence, definitional mismatch, staleness, calendar convention, duplicate keys) — none of that lives in Layer 1. Layer 1's only job is to be a perfect, internally-consistent, atomic-grain truth with known injected labels in `injected_events`.
