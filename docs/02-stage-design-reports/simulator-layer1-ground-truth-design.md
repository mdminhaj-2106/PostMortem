# Simulator — Layer 1 Ground Truth — Design Report

**Status:** Design complete, pre-implementation. Blocks every other stage — nothing downstream has data to run against until this exists.

---

## 1. Unit of generation: the episode

Per the architecture report, Component A/B training needs "several hundred episodes," each independently labeled and stratifiable into train/val/test. So the generator's output unit is an **episode**, not one long continuous timeline:

- Each episode is a fresh fake business: its own customers, products, day-zero baselines.
- Each episode spans `n_days` (default 120: enough runway for a delayed/ramping cause like product-outage churn to fully show up, plus pre/post buffer).
- **Revised — event count is a distribution, not a fixed 0-or-1.** Real businesses aren't single-cause: an outage triggers a panic marketing cut, or an unrelated competitor launch just happens to land in the same quarter as a seasonal dip. Draw the number of events per episode from weights like `{0: 0.35, 1: 0.40, 2: 0.20, 3: 0.05}` (a knob, not a law — retune once Stage 5b actually trains against it). This is what gives Stage 5b (Confounded-Cause Decomposer) real multi-cause data to untangle instead of a stage with nothing to practice on — see §1.2.
- Event type, severity, onset shape, and affected segment/product are randomized per event instance within declared ranges (§1.1–§1.3), so training data covers a spread — easy, obvious cases *and* brutal, ambiguous ones — not one canned shape per cause.

Target: ~400 episodes. Balance is now tracked per *event count* and *event type* (not a clean 5-way split), stratified downstream at training time.

### 1.1 Real-data grounding — bootstrap off Olist, don't hand-tune distributions

Pure hand-authored gaussians read as synthetic and hide exactly the messiness real business data has for free. Instead of inventing customer/product/order distributions from scratch, **bootstrap-resample the real Olist Brazilian e-commerce dataset** (public, ~100k orders, 2016–2018, real customer states, real product categories, real order values, real reviews, real delivery-date slippage) as each episode's starting population:

- **Customers**: sample `(state/region, historical order frequency)` pairs from Olist's real customer distribution instead of a uniform 3-region split — real geography is lumpy (São Paulo dominates), not evenly spread.
- **Products**: sample from Olist's real ~70 product categories and their real (long-tailed, not gaussian) price distributions.
- **Order timing / seasonality**: bootstrap the *shape* of Olist's actual daily order-count series (real Black Friday spike, real post-holiday dip, real day-of-week pattern) instead of a hand-tuned sine wave for `seasonality_factor` — this is a real calendar effect the significance classifier has to learn isn't a story, not one we invented to be learnable.
- **Delivery slippage**: Olist already has `order_delivered_date` vs `order_estimated_delivery_date` — reuse that real lateness distribution as the natural baseline noise for `product_reliability`, so an injected outage is a *departure* from real baseline flakiness, not a departure from a suspiciously perfect baseline.
- **Reviews**: Olist's real review text/scores become the pool Stage 6 draws from later (not built now, but customer/product keys should already line up with Olist's so that hookup is a join, not a rewrite).

This promotes the architecture report's "optional hybrid enrichment" from optional polish to the default approach — our injected events are the controlled deviation *from* a real backbone, not from an invented one.

### 1.2 Causal chaining and coincidence — how multiple events actually relate

Two independent mechanisms produce multi-event episodes, and they mean different things downstream:

- **Reactive chaining** (`triggered_by_event_id`, §2): an event probabilistically spawns a second one as a response — e.g. `product_outage` has a ~60% chance of triggering a reactive `marketing_cut` a few days later (panic pause on paid acquisition while the team firefights), `competitor_launch` has a ~40% chance of triggering a pricing response. These two effects genuinely overlap and compound in the data — this is the realistic version of "confounded cause," and it's exactly the shape Stage 5b exists to decompose.
- **Coincidental overlap**: independent of chaining, two unrelated events can simply land in overlapping day-ranges by chance (an inventory shortage and an unrelated regional competitor launch happen to both be live in the same window) — mechanically this just means event windows aren't prevented from overlapping when sampled, not new machinery.

Both cases matter for training: chained events have a real causal link the model *could* in principle infer from timing (outage always precedes its reactive cut); coincidental ones don't, and the honest answer for those is "two things happened, only partially separable" — the ability to say that, not just decline outright, is Stage 5b's whole point.

### 1.3 Severity, onset shape, and mitigation — not every event looks the same

- **Severity tiers**: `minor` / `moderate` / `severe`, each a magnitude range. `minor` events are deliberately allowed to land *below* Stage 2's significance threshold — sub-threshold "near-miss" cases are exactly the boundary data a calibrated classifier needs, not just clean positives and clean negatives.
- **Onset shape isn't fixed per event type.** Each event type has a *typical* onset (marketing_cut usually steps, product_outage usually ramps) but reality doesn't always cooperate — assign onset shape per event instance from `{step, ramp, spike_decay, delayed}`, weighted toward the type's typical shape but not locked to it.
- **Mitigation, not just a clean end boundary**: an event can carry a `mitigation_day_offset` — the outage gets fixed, inventory gets restocked, ad spend gets restored — after which the effect decays back toward baseline, and that decay can be `complete` or `partial` (a mitigation_completeness in [0,1]: reputation damage from an outage can linger as a small permanent step-down in baseline satisfaction even after the outage itself is fixed). This replaces a hard `end_day_offset` cutoff with something that actually looks like a company responding to a problem.
- **Uneven effect across segments/regions**: rather than an event applying identically everywhere or entirely to one `affected_segment`, give it a `segment_multiplier` — mostly close to 1.0 (roughly even), occasionally sharply uneven (an outage that's technically global but hits Enterprise harder because they lean on the affected feature more).

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
  satisfaction, competitor_activity, churn_rate,
  volatility_multiplier            -- see §3a: calm vs turbulent stretches, not constant noise

orders                           -- atomic; revenue/AOV/orders-count derive from this
  order_id, episode_id, day_offset, customer_id, product_id, quantity, unit_price

support_tickets                  -- atomic; complaint-rate KPI derives from this
  ticket_id, episode_id, day_offset, customer_id, category

injected_events                  -- ground truth. Held out — never fed to the pipeline as input.
                                  -- multiple rows per episode now allowed (§1.2).
  event_id, episode_id, event_type, severity, onset_type,
  start_day_offset, end_day_offset,
  mitigation_day_offset (nullable), mitigation_completeness (nullable),
  magnitude, segment_multiplier, affected_segment (nullable), affected_product_id (nullable),
  triggered_by_event_id (nullable, self-FK — reactive chaining, §1.2),
  description
```

`active_customers(t)` = count of customers where `signup_day_offset <= t` and (`churned_day_offset` is null or `> t`) — derived, not stored. `revenue(t)` = `sum(quantity * unit_price)` for that day's orders — also derived.

## 3. Generation order (per episode, per day)

Structural equations, in dependency order — each day's state feeds the next day where there's momentum (churn, active-customer base). Every event-conditioned step below now applies its effect through a shared **effect curve** shaped by that event instance's `onset_type` and mitigation (§1.3), not a fixed step function — and when more than one event's window covers the same day, their effects on a variable **stack additively/multiplicatively as appropriate**, they don't overwrite each other (this is what makes chained/coincidental events actually confound in the data instead of just being labeled that way).

0. **Volatility regime** (§3a) — draw/carry forward `volatility_multiplier` for this day before anything else; every noise draw below is scaled by it.
1. `seasonality_factor` — bootstrapped from Olist's real daily order-count shape (§1.1), not a hand-tuned sine wave. Deterministic given the episode's calendar mapping; it's the thing Stage 2 must learn to *not* mistake for a real signal.
2. `marketing_spend` = baseline (Olist-informed) + noise·volatility. Any live `marketing_cut` event applies its effect curve here.
3. `product_reliability` = baseline (Olist delivery-slippage-informed, §1.1) + noise·volatility. Any live `product_outage` applies its effect curve here, including partial post-mitigation reputation drag (§1.3).
4. `competitor_activity` = baseline + noise·volatility. Any live `competitor_launch` applies its effect curve here.
5. `traffic` = `f(marketing_spend, seasonality_factor, noise·volatility)`.
6. `conversion_rate` = `f(pricing=baseline, product_reliability, noise·volatility)`.
7. Sample `orders_count ≈ traffic × conversion_rate` (Poisson draw around that expected count, scaled by `volatility_multiplier`), then generate that many `orders` rows: pick `customer_id` (existing active customer or new signup, drawn from the Olist-bootstrapped population), `product_id` (any live **inventory_shortage** zeroes/reduces sampling weight for `affected_product_id`, by its own effect curve — not an instant hard zero unless severity is `severe`), `quantity`, `unit_price` (Olist-informed price distribution, small noise).
8. Sample `support_tickets` count as `f(product_reliability, noise·volatility)`, generate that many rows with `customer_id`.
9. `satisfaction` = `f(support_complaints_count, noise·volatility)`.
10. `churn_rate` = `f(satisfaction, competitor_activity, noise·volatility)`, with any live event's `segment_multiplier` (§1.3) applied per customer's segment — so "broad-based" vs "segment-concentrated" is a continuous knob per event instance, not two hardcoded behaviors. Apply as a per-customer Bernoulli draw among active customers → set `churned_day_offset` for the ones who churn that day.
11. **product_outage**'s default onset is delayed/ramping: its churn effect curve is typically a function of *cumulative* complaints since onset rather than a same-day step — giving it the "delayed, ramping onset" fingerprint from the architecture report by default, while §1.3 still allows an atypical instance to deviate.

**Pure-noise episodes** have zero rows in `injected_events` and every variable above is just baseline + noise·volatility, no effect curve ever applied. This is the actual mechanism behind "ability to decline": nothing about a quiet stretch inside an event episode differs mechanically from a full noise episode — the only difference is whether an effect curve happens to be live that day.

### 3a. Volatility regimes — why noise isn't constant

Real businesses have calm quarters and chaotic quarters even absent any injected cause. Rather than a fixed noise standard deviation for the whole episode, draw a `volatility_multiplier` per ~3–4 week block (a simple regime-switch — most blocks ≈1.0x, occasionally a turbulent block ≈2–3x), held in `daily_state` so it's inspectable. This is what makes some pure-noise episodes genuinely choppy and some event episodes genuinely subtle — matching "sometimes very easy, sometimes very brutal" instead of every episode having the same, easily-learnable noise floor.

## 4. Open parameters (need a value, not a design decision — pick defaults and move on)

- `n_days` = 120, ~400 episodes, 2–4 products/episode sampled from Olist categories — all easy to tune after the first end-to-end run once Stage 2/Component A actually trains on it.
- Event-count weights `{0: 0.35, 1: 0.40, 2: 0.20, 3: 0.05}`, severity-tier magnitude ranges, chaining probabilities (outage→cut ~60%, competitor→pricing ~40%), volatility block length (~3–4 weeks) and multiplier range (~1.0–3.0x): all knobs, start here, retune once the classifiers are actually training against the output and either drowning in noise or finding it too easy.

## 5. Explicitly out of scope for Layer 1

- CRM notes / review text *generation* — Olist's real review text is bootstrapped for population realism (§1.1) now, but wiring it into Stage 6's evidence pipeline (chunking, embedding, entity extraction) is that stage's job, not this one.
- Pricing-change and seasonal/regional-economic cause categories (PRD's fuller cause list) — the architecture report's scope guard already caps this at the 4 injected event types (+ reactive chaining between them, §1.2) + noise; the other cause labels in Component B's label space stay unimplemented for the prototype.

## 6. What this hands to Layer 2

Layer 2's SQL views read these 7 tables directly and are responsible for all the degradation (grain, cadence, definitional mismatch, staleness, calendar convention, duplicate keys) — none of that lives in Layer 1. Layer 1's only job is to be a perfect, internally-consistent, atomic-grain truth with known injected labels in `injected_events`.
