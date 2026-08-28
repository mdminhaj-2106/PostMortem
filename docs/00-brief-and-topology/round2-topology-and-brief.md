# PS3 — Round 2 Brief Summary & Locked System Topology
## AIC 2026, BusinessIntelligence.ai

**Purpose of this doc:** carry forward everything from the pre-Stage-1 working session so future sessions (or teammates) don't need the original chat transcript — the brief's actual requirements, the gap-check against the original architecture, the differentiation strategy, the locked 11-stage topology (with per-stage job descriptions), and the working method used to design each stage. Stage-by-stage design reports are separate docs in this project.

---

## 1. Round 2 Confirmation & Brief

Advanced from Round 1 (Solution Framework: 2-3 slide deck + 2-3 min video) to Round 2 (Prototype Development). The official Round 2 brief (PDF, 4 problem tracks: ControlPlane.ai, PatientTriage.ai, BusinessIntelligence.ai [ours, PS3], DigitalTwin.ai) gives, for PS3 specifically:

**8 Round 2 objectives** (paraphrased from the brief):
1. Detect and prioritize material KPI movement
2. Reconcile heterogeneous data sources
3. Rank likely drivers/causes
4. Generate persona-specific narratives
5. Communicate uncertainty / be able to abstain
6. Recommend actions grounded in levers and decision rights
7. Learn from analyst/business-user feedback
8. Operate within security, cost, latency, and scalability constraints

**10 real-world complexities** the brief wants addressed: multiple interacting drivers; mismatched refresh cadences/grains; inconsistent KPI definitions/hierarchies/calendars; sparse history; materiality; contradictory evidence; role-based personalization; row/column-level security; model drift; LLM economics.

**Minimum prototype checklist** (~10 items, paraphrased): 3-5 KPIs across 2-3 sources; a semantic contract; 2+ personas; specific test scenarios; an LLM-vs-non-LLM cost/call breakdown; runtime telemetry.

**Deliverables:** business proposal, working prototype, public GitHub repo, demo video, README.

---

## 2. Gap-Check Against the Original (Round 1) Architecture

The original `ps3-architecture-report.md` was scored against the 8 objectives:

- **Strong already:** driver ranking (#3), uncertainty/abstention (#5)
- **Partial:** multi-KPI prioritization (#1 — original system only ever handled one KPI at a time), persona narratives (#4 — had exec-vs-analyst depth, not genuinely different narratives/actions per role), recommendations (#6 — missing the "decision rights" governance concept entirely)
- **Missing entirely:** cross-source data reconciliation (#2), feedback/learning loop (#7 — the Memory agent only retrieved, didn't learn from corrections), security/cost/latency constraints (#8)

Same treatment against the 10 complexities: roughly half already handled by the original diagnostic core (Components A-E), the other half (cadences, definitions, calendars, security, LLM economics) requiring an entirely new data-platform layer that didn't exist before Round 2.

**The reframe:** Round 1 asked for a single-metric "KPI storytelling engine." Round 2 quietly reclassifies the whole thing — the original diagnostic brain (Components A-E) is now just one subsystem inside a larger governed, multi-KPI, multi-persona, cost-aware platform. The brief is now grading the nervous system around the brain (governance, security, economics, feedback), not just the brain itself. The brief's principle that "the LLM is never the source of quantitative truth" is effectively the founding principle, now written into the rubric — but it has to be a visible, inspectable breakdown in the running prototype, not a claim in a report.

---

## 3. Differentiation Strategy

**First finding (market-level):** the "hybrid deterministic components + LLM-only-narration + abstain-when-noise" positioning isn't just common among student teams — real 2026 commercial RCA/BI-diagnostic products (Datadog Watchdog, Dynatrace Davis AI, Sherlocks.ai, NeuBird, Tellius, Statspresso) already market themselves this way. Where even those commercial products fall short: none explicitly decomposes two overlapping/confounded causes (everyone ranks one top cause), cold-start handling is hand-waved, nobody demos live.

**Sharper finding (peer-level, the one that actually matters for judging):** since the Round 2 brief now explicitly writes out the hybrid-deterministic+LLM-narration+abstain pattern as a graded requirement, every team that reads the brief carefully will converge on the same shape — "we thought of the shape" stopped being a differentiator the moment the brief was published. The shared PRD example scenario (8% drop, North -15%, Enterprise -14%, Product A -21%) being reused as everyone's headline demo compounds the "same idea" impression even beyond the shared architecture.

**Actual separation levers for near-identical teams:**
- Actually train models and show real numbers (confusion matrix, false-causality rate) instead of prompt-faking ML
- Go deep on the confounded/overlapping-cause problem (Stage 5b) that a one-week team will skip
- Don't lead the demo with the PRD's own scenario — build a harder, original one
- Make the demo live and judge-directed instead of a canned walkthrough (this is a presentation decision, not a system component — deliberately kept out of the topology to keep it MECE)

---

## 4. Locked System Topology (with per-stage job descriptions)

Defined before Stage 1 began; this is the authoritative stage list, naming, and job description for each stage — later summaries should match it exactly.

1. **Data Reconciliation & Ingestion** — pull from heterogeneous sources at different grains/cadences and normalize into one canonical event stream. Nothing downstream can trust its inputs until this exists. *Design report complete: `claude/ps3-stage1-reconciliation-design.md`.*
2. **Per-KPI Significance Detection** — for each individual KPI stream, decide Normal / Emerging / Significant / Structural. Runs independently per metric (old Component A, run N times in parallel). *Being designed in parallel by a teammate, tracked outside this project; reconcile interfaces once shared.*
3. **Cross-KPI Correlation & Prioritization** — given several KPIs flagged as moved in the same window, decide whether they're one underlying story told twice or genuine coincidences, and rank which cluster deserves investigation first by business impact. *In progress.*
4. **Dimensional Decomposition** — break a flagged movement (or cluster) down by region/segment/product/channel. Purely descriptive, no cause-guessing yet.
5. **Fingerprint / Cause-Signature Classification (5a)** — read the shape of the decomposition (onset, spread, entropy) and hypothesize the cause family.
   - **5b. Confounded-Cause Decomposer** — branches off 5a when signature confidence is split, not a fallback but a real fork: when the fingerprint doesn't cleanly point to one cause, attribute contribution across the overlapping causes instead of forcing a top-1 pick. The sharpest differentiator — a named, visible component, not a footnote inside 5a.
   - **5c. Cold-Start / Analogy Handler** — branches off Stage 4 when history is thin, runs instead of or alongside 5a: for a KPI/product/segment with little history, borrow a fingerprint from the nearest analogous case and explicitly label the confidence as "borrowed," not native.
6. **Evidence Retrieval & Linking** — pull unstructured evidence (CRM, tickets, reviews), tag it before/during/after the changepoint, and attach lineage + freshness metadata to every snippet.
7. **Hypothesis Debate & Ranking** — combine 5a/5b/5c output + Stage 6 evidence into a ranked hypothesis list with Known/Likely/Possible/Unknown buckets.
8. **Counterfactual / Consequence Quantification** — for the top-ranked hypothesis (or each contributing cause from 5b), estimate what the KPI would look like without it — a number and an interval, not a paragraph. What stops recommendations from being delusional.
9. **Recommendation Assembly** — turn the quantified diagnosis into the brief's exact structure: driver → lever → action → expected impact → owner → confidence → monitoring plan.
10. **Persona Narrative Routing** — same underlying finding, reframed into different narrative and different recommended action per role — not just more/less detail.
11. **Narration (LLM-only)** — turn the final structured object into prose. Nothing upstream of this stage is allowed to touch narrative language.

**5 cross-cutting services** (not sequential — consulted by multiple stages):
- **KPI Semantic Contract** — definitions, thresholds, lineage rules, hierarchy. Consulted by Stages 1, 2, 4, 5.
- **Security & Access Filter** — row/column/domain-level gating on what data and output a given user is shown. Applied at Stage 10's output, before narration reaches anyone.
- **Decision Rights** — distinct from Security: who is authorized to act on a recommendation, not who can see it. Lives inside Stage 9's "owner" field and Stage 10's routing — deliberately not merged with Security, since seeing ≠ acting.
- **Learning & Memory** — stores past investigations, retrieves similar past fingerprints into Stages 5/7, and absorbs analyst corrections/overrides back into training data. Replaces the old "Memory agent," split cleanly into retrieval-in and correction-in.
- **Telemetry & Cost Governor** — wraps every stage, tracking latency/calls/tokens, and can decide routing (cheap heuristic vs. expensive model call) for cost-sensitive stages like 6 and 11.

Also: the Calendar Dimension reference table and the Identity Resolution Graph (both introduced during Stage 1 design) sit alongside these five as additional cross-cutting services scoped specifically to reconciliation — see the Stage 1 report for detail. The live/judge-directed demo was deliberately excluded from this list — it's a presentation decision about how the pipeline is shown, not a piece of the pipeline, and keeping it out keeps this topology MECE.

---

## 5. Working Method (apply to every remaining stage)

For each stage/design item, in order:
1. Minhaj gives his own instinct first, drawn out via leading questions rather than Claude proposing first.
2. Claude ranks/amends that instinct against the Round 2 brief's actual requirements, naming established real-world techniques where one exists.
3. Move to the next open design item.

Each finished stage gets written up as its own design report (two-layer structure like Stage 1: the mechanism/scenarios, then reused-machinery cross-references, then an output contract to the next stage) and saved to this project — not left in chat, so sessions can pick up cold without re-deriving context.

**Chat-hygiene note:** don't paste full doc contents back into chat as a way of "confirming" — reference or summarize instead. Docs live here for a reason.
