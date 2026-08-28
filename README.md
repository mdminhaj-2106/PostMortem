# PS3 — BusinessIntelligence.ai
### Accenture Innovation Challenge (AIC) 2026 — Round 2 Prototype

A KPI storytelling / root-cause diagnostic engine: detects material KPI movement, reconciles it across messy heterogeneous sources, decomposes and fingerprints the likely cause, debates competing hypotheses against real evidence, quantifies the counterfactual, and narrates a persona-specific, action-grounded recommendation — with the explicit ability to say **"normal variation, no story"** instead of manufacturing a plausible-sounding cause.

This folder is the working scaffold for the team: design docs first, code structure second, built directly from the design reports and architecture already agreed on. Nothing in `pipeline/` is implemented yet — see each stage's `README.md` for status.

---

## 1. Orientation — read these first

1. [`docs/00-brief-and-topology/round2-topology-and-brief.md`](docs/00-brief-and-topology/round2-topology-and-brief.md) — the Round 2 brief's actual requirements, the gap-check against Round 1, the differentiation strategy, and the **locked 11-stage topology** with per-stage job descriptions. Start here.
2. [`docs/01-architecture/architecture-report.md`](docs/01-architecture/architecture-report.md) — the original Round 1 differentiated architecture (Components A–E: significance classifier, fingerprint classifier, SCM/counterfactuals, multi-agent debate, evidence pipeline) that the Round 2 topology builds on top of.
3. `docs/02-stage-design-reports/` — one design report per finished stage, in the two-layer format (mechanism/scenarios → reused machinery → output contract) described in the topology doc's working method.
4. [`docs/00-brief-and-topology/round1-pitch-content.md`](docs/00-brief-and-topology/round1-pitch-content.md) — the Round 1 pitch deck/video content, for reference on positioning and the running example (the "-8% revenue, North -15%, Enterprise -14%, Product A -21%" scenario used throughout).

**Chat-hygiene / doc-hygiene note (carried over from the topology doc):** don't paste full doc contents back into chat, Slack, etc. as a way of "confirming" — reference or summarize instead. These docs are the source of truth so any session or teammate can pick up cold.

---

## 2. Locked 11-Stage Pipeline Topology

| # | Stage | Design status | Docs |
|---|---|---|---|
| 1 | Data Reconciliation & Ingestion | **Design complete** | [`stage1-reconciliation-design.md`](docs/02-stage-design-reports/stage1-reconciliation-design.md) |
| 2 | Per-KPI Significance Detection (Relevance Extraction & Change Classification) | **Design complete** | [`stage2-relevance-extraction-architecture.md`](docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md) |
| 3 | Cross-KPI Correlation & Prioritization | **Design complete** | [`stage3-cross-kpi-correlation-prioritization.md`](docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md) |
| 4 | Dimensional Decomposition | **Implementation plan ready** (blocked on confirming Stage 2's function interface — see plan §4/§7) | [`stage4-dimensional-decomposition-implementation-plan.md`](docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md) |
| 5a | Fingerprint / Cause-Signature Classification | Not yet designed | — |
| 5b | Confounded-Cause Decomposer (branches off 5a) | Not yet designed — flagged as the sharpest differentiator, don't skip | — |
| 5c | Cold-Start / Analogy Handler (branches off Stage 4) | Not yet designed | — |
| 6 | Evidence Retrieval & Linking | Not yet designed | — |
| 7 | Hypothesis Debate & Ranking | Not yet designed | — |
| 8 | Counterfactual / Consequence Quantification | Not yet designed | — |
| 9 | Recommendation Assembly | Not yet designed | — |
| 10 | Persona Narrative Routing | Not yet designed | — |
| 11 | Narration (LLM-only) | Not yet designed | — |

**Cross-cutting services** (consulted by multiple stages, not sequential steps):

| Service | Introduced by | Consulted by |
|---|---|---|
| KPI Semantic Contract | Stage 1 | Stages 1, 2, 4, 5 |
| Calendar Dimension | Stage 1 | Stage 1 (and any stage bucketing by calendar convention) |
| Identity Resolution Graph | Stage 1 | Stages 1, 6 |
| Security & Access Filter | Topology (not yet designed) | Stage 10's output |
| Decision Rights | Topology (not yet designed) | Stage 9's owner field, Stage 10's routing |
| Learning & Memory | Topology (not yet designed) | Stages 1, 5, 7 (retrieval-in + correction-in) |
| Telemetry & Cost Governor | Topology (not yet designed) | Wraps every stage |

Full per-stage job descriptions and the rationale for every naming/scoping decision live in the topology doc — this table is a status index, not a replacement for it.

---

## 3. Repository Layout

```
ps3-businessintelligence-ai/
├── README.md                          <- you are here
├── docs/
│   ├── 00-brief-and-topology/         <- brief, gap-check, differentiation strategy, locked topology
│   ├── 01-architecture/               <- Round 1 differentiated architecture report
│   └── 02-stage-design-reports/       <- one design report per finished stage
└── pipeline/
    ├── stage01_reconciliation_ingestion/
    ├── stage02_significance_detection/
    ├── stage03_cross_kpi_correlation/
    ├── stage04_dimensional_decomposition/
    ├── stage05a_fingerprint_classification/
    ├── stage05b_confounded_cause_decomposer/
    ├── stage05c_cold_start_analogy_handler/
    ├── stage06_evidence_retrieval/
    ├── stage07_hypothesis_debate_ranking/
    ├── stage08_counterfactual_quantification/
    ├── stage09_recommendation_assembly/
    ├── stage10_persona_narrative_routing/
    ├── stage11_narration/
    ├── cross_cutting/
    │   ├── kpi_semantic_contract/
    │   ├── calendar_dimension/
    │   ├── identity_resolution_graph/
    │   ├── security_access_filter/
    │   ├── decision_rights/
    │   ├── learning_memory/
    │   └── telemetry_cost_governor/
    └── simulator/
        ├── layer1_ground_truth/       <- perfect, atomic-grain generating engine (held out, scoring only)
        └── layer2_observed_sources/   <- SQL-view degradation layer teams actually ingest from
```

Each `pipeline/` folder currently holds only a `README.md` stating its job description, design status, and links to the relevant design doc(s) — this is a navigable skeleton to build against, not yet code. As each stage gets designed and implemented, its design report goes in `docs/02-stage-design-reports/` and its code lands in the matching `pipeline/` folder (see Stage 4's implementation plan for the level of detail — exact I/O schemas, module breakdown, build order, test plan — expected before a stage is considered ready to implement).

---

## 4. Working Method (for every remaining design item)

1. Minhaj gives his own instinct first, drawn out via leading questions.
2. The instinct gets ranked/amended against the Round 2 brief's actual graded requirements, naming established real-world techniques where one exists.
3. Move to the next open design item.

Each finished stage gets written up as its own design report — mechanism/scenarios, then reused-machinery cross-references, then an explicit output contract to the next stage — and saved into `docs/02-stage-design-reports/`, not left in chat.

---

## 5. Recurring Design Principles (apply when designing any remaining stage)

These principles carried the differentiation across every finished stage so far — reach for them before inventing something new:

1. **Tiered confidence escalation** — cheap/deterministic checks first, expensive/human checks last, every tier tagging the confidence it achieved.
2. **Materiality-gated action** — never resolve, recompute, or rank based on whether a number moved; only whether a *decision* would flip.
3. **Causal-graph-constrained reasoning** — when corroborating evidence or a causation check is needed, consult only what the SCM/DAG says is structurally connected; never blind-scan everything.
4. **Declare, don't infer, what can be declared** — source bias, definitions, calendar convention, the DAG itself: authored once at design time; live inference is the fallback, not the default.
5. **Uncertainty that propagates and compounds** — a confidence/imputation tag must survive and appropriately widen through every downstream consumer.
6. **Decline over false confidence** — an unresolved conflict, unfillable gap, ambiguous identity match, or genuinely noisy episode should surface as an explicit unresolved/normal state, not a forced answer.
7. **Correction has a name and an owner** — restatement, not silent overwrite, with the original recommendation's owner explicitly notified.

---

## 6. Round 2 Deliverables Checklist

Per the brief: business proposal, working prototype, public GitHub repo, demo video, README. Minimum prototype checklist: 3–5 KPIs across 2–3 sources, a semantic contract, 2+ personas, specific test scenarios, an LLM-vs-non-LLM cost/call breakdown, runtime telemetry. See the topology doc §1 for the full, unabridged list of 8 objectives and 10 real-world complexities being graded against.
