# Stage 7 — Hypothesis Debate & Ranking
## Detailed Implementation Architecture — AIC / PS3 BusinessIntelligence.ai

**Status:** Architecture proposed after design interview; ready for implementation after final review  
**Stage:** 7  
**Consumes:** Stage 5a, Stage 5b, Stage 5c, Stage 6, and upstream structural context  
**Produces:** Ranked, evidence-backed hypotheses for Stage 8  
**Primary design goal:** Convert heterogeneous analytical and observational evidence into a ranked hypothesis set without turning model confidence into causal certainty.

---

# 1. Purpose

Stage 7 is the **evidence synthesis and hypothesis resolution layer**.

Stages 1–4 establish what changed and where. Stages 5a–5c characterize plausible causes and handle confounding/cold-start limitations. Stage 6 supplies observational evidence. Stage 7 brings those pieces together and asks:

> Given all available evidence, which constrained hypotheses are best supported, which are contradicted, and how confident should we be?

Stage 7 is the first stage permitted to **rank competing causal hypotheses**.

It does **not** perform counterfactual estimation, causal-effect calculation, new dimensional decomposition, or recommendation generation.

The central separation is:

```text
Stage 5a probability
    ≠
Stage 5b contribution
    ≠
Stage 6 evidence
    ≠
Stage 7 confidence
```

Stage 7 must preserve those distinctions rather than collapse them into one opaque score.

---

# 2. Architectural Principles

## 2.1 Evidence synthesis, not evidence replacement

Stage 7 consumes upstream outputs rather than re-running their analytical logic.

It must not:

- rediscover anomalies;
- redo Stage 4 dimensional decomposition;
- retrain Stage 5 models;
- recompute Stage 5b attribution;
- reinterpret 5c borrowing as native evidence.

---

## 2.2 Hypotheses are first-class objects

A hypothesis may represent:

```text
single cause
```

or:

```text
constrained compound cause
```

Examples:

```text
product_outage
```

```text
product_outage + marketing_cut
```

The second form is especially important when Stage 5b returns:

```text
NON_IDENTIFIABLE_JOINT
```

A joint component must remain joint downstream.

Stage 7 may never manufacture a numerical split for a 5b joint component.

---

## 2.3 Constrained hypothesis generation

Stage 7 may generate compound hypotheses, but only from:

1. Stage 5 candidate causes;
2. Stage 5b joint components;
3. declared cause relationships;
4. structurally compatible combinations supported by available evidence.

It must not freely invent arbitrary explanations.

For example:

```text
product_outage + marketing_cut
```

may be generated if those causes are candidates and their relationship is declared or supported.

But:

```text
customer dissatisfaction + management failure
```

must not appear merely because an LLM or text parser can imagine it.

The hypothesis vocabulary is bounded by the declared cause families and relationship configuration.

---

# 2.4 Confidence is not a probability by default

Stage 5a probabilities are classifier outputs.

Stage 7 confidence buckets are evidence-resolution outcomes:

```text
KNOWN
LIKELY
POSSIBLE
UNKNOWN
```

A Stage 5a probability of `0.92` does not automatically imply `KNOWN`.

Likewise, a low Stage 5a probability cannot automatically eliminate a hypothesis when strong independent Stage 6 evidence supports it.

---

# 2.5 Contradiction is first-class

Evidence can support or contradict a hypothesis.

Contradiction must be retained explicitly rather than silently hidden inside a numerical score.

A hypothesis therefore carries:

```text
supporting evidence
contradicting evidence
neutral evidence
```

A contradiction normally downgrades confidence.

A sufficiently strong contradiction can cause the hypothesis to become `UNKNOWN` or be removed from the ranked candidate set, depending on the configured policy.

---

# 2.6 Abstention is correct behavior

Stage 7 must be allowed to conclude:

```text
ABSTAIN
```

when the evidence does not support a defensible ranking.

A forced winner is worse than an explicit unresolved result.

---

# 2.7 Preserve uncertainty from upstream stages

Important inherited constraints:

```text
5b NON_IDENTIFIABLE_JOINT
    → never split downstream

5c BORROWED
    → maximum confidence bucket = POSSIBLE
       unless independent native evidence upgrades it

5c absent / no analog
    → no invented cause

limited evidence
    → confidence is capped accordingly
```

---

# 3. End-to-End Architecture

```text
                  ┌──────────────┐
                  │   Stage 5a   │
                  │ fingerprint  │
                  └──────┬───────┘
                         │
                  candidate causes
                         │
                  ┌──────▼───────┐
                  │   Stage 5b   │
                  │ contribution │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │   Stage 5c   │
                  │ cold-start   │
                  └──────┬───────┘
                         │
                         │
                  ┌──────▼───────┐
                  │    Stage 6   │
                  │ observations │
                  └──────┬───────┘
                         │
                         ▼
              ┌──────────────────────┐
              │        STAGE 7       │
              │                      │
              │ 1. Input validation  │
              │ 2. Candidate assembly│
              │ 3. Hypothesis build  │
              │ 4. Evidence linking  │
              │ 5. Support analysis  │
              │ 6. Contradiction     │
              │ 7. Structural check  │
              │ 8. Confidence resolve│
              │ 9. Rank              │
              │10. Abstention        │
              │11. Output validation │
              └──────────┬───────────┘
                         │
                         ▼
                    Stage 8
```

---

# 4. Inputs

Stage 7 consumes the following structured inputs.

## 4.1 Stage 5a result

Required information:

```text
cluster_id
window
fingerprint_features
cause_probabilities
routing_decision
confidence_tier
```

Stage 7 uses `cause_probabilities` as analytical evidence.

It does not relabel them as contribution shares.

---

## 4.2 Stage 5b result

When Stage 5b was invoked:

```text
kpi
window
observed_deviation
contributions
unexplained_share
fit_quality
identifiability_verdict
```

The contribution vector is treated as movement decomposition evidence.

A joint component such as:

```text
product_outage + marketing_cut
```

remains a single hypothesis component.

---

## 4.3 Stage 5c result

When applicable:

```text
thin slice
analog
borrowed percentile
confidence_tier = BORROWED
```

This is explicitly weaker than native evidence.

A borrowed signal can support a hypothesis but cannot, by itself, produce `KNOWN` or `LIKELY`.

---

## 4.4 Stage 6 result

Stage 6 supplies observational evidence.

Stage 7 should consume structured evidence records containing, where available:

```text
evidence_id
source_type
source_identifier
timestamp
entity_reference
candidate_causes
support_direction
strength
provenance
```

Stage 7 should not require free-text evidence interpretation in the core implementation.

If Stage 6 provides text-derived evidence, it should already be converted into structured evidence assertions.

---

## 4.5 Structural context

Stage 7 can consume:

```text
declared KPI DAG
cause relationships
expected direction
expected lag
cause dependencies
```

This context is used for plausibility.

It is not causal proof.

---

# 5. Input Eligibility Gate

Before reasoning, Stage 7 validates:

```text
cluster identity
window consistency
Stage 5 outputs refer to same cluster/window
Stage 6 evidence refers to same investigation window
cause names belong to declared vocabulary
5b joint components are structurally valid
5c confidence restrictions are present
```

Invalid input should fail loudly.

Stage 7 must not silently repair incompatible upstream contracts.

---

# 6. Stage 7 Processing Pipeline

```text
Step 0 — Validate inputs

Step 1 — Assemble candidate causes

Step 2 — Build constrained hypotheses

Step 3 — Attach Stage 5 analytical evidence

Step 4 — Attach Stage 6 observational evidence

Step 5 — Evaluate support

Step 6 — Evaluate contradiction

Step 7 — Evaluate structural plausibility

Step 8 — Resolve evidence

Step 9 — Assign confidence bucket

Step 10 — Rank all surviving candidates

Step 11 — Determine abstention

Step 12 — Validate and emit output
```

---

# 7. Step 1 — Candidate Assembly

Candidate causes originate from:

### Source A — Stage 5a

Include causes whose probability is above a configurable candidate floor.

Example:

```yaml
candidate_probability_floor: 0.05
```

The full probability vector is preserved even if some causes do not become ranked hypotheses.

---

### Source B — Stage 5b

Include:

```text
identified cause
```

and:

```text
NON_IDENTIFIABLE_JOINT component
```

A joint component is represented as one candidate.

---

### Source C — Stage 5c

Include the borrowed cause only when an analog actually produced a supported candidate.

---

### Source D — declared structural relationships

A new candidate may be composed only when:

```text
both component causes are already candidates
AND
the combination is permitted by cause configuration
AND
there is structural/evidence support for considering the combination
```

No arbitrary Cartesian product of causes is permitted.

---

# 8. Step 2 — Hypothesis Construction

A hypothesis has:

```text
hypothesis_id
member_causes
hypothesis_type
```

Example:

```json
{
  "hypothesis_id": "H1",
  "member_causes": ["product_outage"],
  "hypothesis_type": "SINGLE"
}
```

Compound:

```json
{
  "hypothesis_id": "H2",
  "member_causes": [
    "product_outage",
    "marketing_cut"
  ],
  "hypothesis_type": "COMPOUND"
}
```

A 5b joint hypothesis additionally carries:

```text
identifiability = NON_IDENTIFIABLE_JOINT
```

---

# 9. Compound Hypothesis Rules

Compound hypotheses may be created through three mechanisms.

## 9.1 Direct 5b joint component

Highest-confidence source for compound construction.

```text
5b:
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

Stage 7 creates exactly:

```text
H:
product_outage + marketing_cut
```

It does not create independent contribution values for the members.

---

## 9.2 Declared causal dependency

If configuration declares:

```text
product_outage → marketing_cut
```

and evidence supports the relationship, Stage 7 may construct:

```text
product_outage + marketing_cut
```

The compound hypothesis represents the causal sequence, not two independent additive causes.

---

## 9.3 Evidence-supported candidate combination

Two existing candidates may be composed when the evidence indicates both were active in the same window and their combination is allowed by configuration.

This requires corroborating evidence.

Stage 7 must not create every pair:

```text
4 causes → 6 arbitrary pairs
```

unless each pair satisfies the combination policy.

---

# 10. Step 3 — Analytical Evidence Model

Stage 7 maintains analytical evidence separately by source.

```text
AnalyticalEvidence
├── source = STAGE5A
├── source = STAGE5B
├── source = STAGE5C
└── source = STRUCTURAL
```

---

## 10.1 Stage 5a evidence

Store:

```text
probability
rank
margin context
fingerprint support
confidence tier
```

Example:

```json
{
  "source": "STAGE5A",
  "cause": "product_outage",
  "probability": 0.42
}
```

This means:

> Stage 5a considers this cause plausible at this probability.

It does not mean:

> The cause has a 42% contribution to the movement.

---

# 11. Stage 5b Evidence

5b contributes:

```text
contribution
share
fit_quality
identifiability
basis_provenance
```

This is stronger evidence about the **observed movement** than Stage 5a's classifier probability.

For example:

```text
product_outage
contribution = 6.1 KPI units
share = 0.76
```

means the fitted decomposition attributes approximately 76% of the modeled deviation to that cause.

It does not alone prove that the real-world event occurred.

---

# 12. Stage 5c Evidence

5c contributes:

```text
borrowed_percentile
analog_used
confidence_tier = BORROWED
```

This evidence is marked:

```text
evidence_origin = BORROWED
```

A borrowed signal is never treated as equivalent to native evidence.

Hard confidence cap:

```text
BORROWED-only
→ maximum POSSIBLE
```

Independent native evidence may remove the cap.

---

# 13. Step 4 — Stage 6 Evidence Linking

Each Stage 6 evidence item is linked to one or more constrained hypotheses.

Example:

```text
Evidence:
support ticket category = delivery_problem
```

may support:

```text
product_outage
```

and possibly:

```text
inventory_shortage
```

if the structured Stage 6 output says so.

Stage 7 should not reinterpret arbitrary text into new cause labels.

---

# 14. Evidence Direction

Every evidence item should be classified as:

```text
SUPPORTING
CONTRADICTING
NEUTRAL
```

Example:

```text
Evidence:
"marketing spend was reduced beginning two days after outage"

Supports:
product_outage + marketing_cut
```

A direct observation:

```text
"marketing budget was unchanged"
```

contradicts:

```text
marketing_cut
```

---

# 15. Evidence Strength

Use discrete, explainable levels rather than pretending the system knows exact likelihood ratios.

Recommended:

```text
NONE
WEAK
MODERATE
STRONG
DIRECT
```

Interpretation:

| Strength | Meaning |
|---|---|
| NONE | no usable evidence |
| WEAK | weak indirect signal |
| MODERATE | meaningful supporting/contradicting evidence |
| STRONG | multiple or high-quality convergent observations |
| DIRECT | explicit observation establishing the relevant fact |

---

# 16. Evidence Independence

Stage 7 must distinguish:

```text
total evidence count
```

from:

```text
independent evidence count
```

Evidence provenance should support grouping by:

```text
source
entity
incident
timestamp
origin
```

Example:

```text
10 copied CRM notes
```

should not automatically count as 10 independent confirmations.

Output:

```json
{
  "evidence_count": 10,
  "independent_source_count": 1,
  "independent_entity_count": 1
}
```

---

# 17. Evidence Quality

Each hypothesis receives an evidence-quality summary:

```text
freshness
independence
provenance completeness
source reliability
coverage
```

The first implementation should use structured categorical values.

Example:

```json
{
  "freshness": "HIGH",
  "independence": "MODERATE",
  "provenance": "COMPLETE"
}
```

Do not fabricate a precise numeric reliability score unless the source system provides one.

---

# 18. Step 5 — Support Resolution

For every hypothesis:

```text
Stage 5a support
+
Stage 5b support
+
Stage 5c support
+
Stage 6 support
+
structural support
```

are kept separately.

Then derive a structured support assessment.

Example:

```text
Support:
STRONG

Reasons:
- high Stage 5a probability
- large Stage 5b contribution
- direct Stage 6 evidence
- expected temporal ordering
```

The reasons should be enum-backed codes rather than generated prose.

Example:

```text
HIGH_CLASSIFIER_SUPPORT
HIGH_MOVEMENT_CONTRIBUTION
DIRECT_OBSERVATIONAL_SUPPORT
EXPECTED_TEMPORAL_ORDER
```

---

# 19. Step 6 — Contradiction Resolution

Contradictions are evaluated independently of support.

Example:

```text
Hypothesis:
marketing_cut

Support:
Stage 5a = 0.38
Stage 5b = 0.24 contribution share

Contradiction:
finance record says spend unchanged
```

The hypothesis remains visible but confidence is downgraded.

Output:

```text
contradiction_status = PRESENT
confidence_modifier = DOWNGRADED
```

---

# 20. Strong Contradiction

A sufficiently strong contradiction can make a hypothesis:

```text
UNKNOWN
```

or remove it from the ranked set if the contradiction policy explicitly marks it impossible.

The default prototype behavior should prefer:

```text
retain + downgrade
```

over silent deletion.

This preserves auditability.

---

# 21. Step 7 — Structural Plausibility

Stage 7 may use the declared KPI/cause graph to test:

### Direction

Example:

```text
marketing_cut
→ traffic ↓
→ orders ↓
→ revenue ↓
```

Observed:

```text
traffic ↓
orders ↓
revenue ↓
```

This supports the hypothesis.

---

### Timing

Example:

```text
product_outage
→ marketing_cut after 3–10 days
```

Observed:

```text
outage begins
marketing spend falls 5 days later
```

This supports the compound hypothesis.

---

### Dependency consistency

If two causes are declared dependent, Stage 7 should not treat them as unrelated independent explanations.

---

# 22. Structural Rules

Structural evidence can:

```text
support plausibility
support direction
support timing
support compound formation
```

Structural evidence cannot:

```text
prove causation
override direct contradictory evidence
create a candidate cause from nothing
```

This keeps the DAG in its proper role.

---

# 23. Step 8 — Evidence Resolution Model

The initial implementation should use a **hybrid deterministic resolution model**.

Do not use an arbitrary weighted score.

The resolver operates in two layers.

## Layer A — Evidence classification

For each hypothesis:

```text
analytical_support
observational_support
structural_support
contradiction
evidence_quality
```

are classified into discrete states.

---

## Layer B — Resolution rules

Rules determine:

```text
confidence bucket
ranking tier
abstention
```

Example:

```text
DIRECT observational evidence
+
strong analytical support
+
no material contradiction
→ KNOWN
```

```text
multiple independent supporting sources
+
strong analytical support
+
no material contradiction
→ LIKELY
```

```text
meaningful support
+
remaining uncertainty
→ POSSIBLE
```

```text
insufficient support
OR unresolved conflict
→ UNKNOWN
```

---

# 24. Confidence Bucket Definitions

## KNOWN

A hypothesis is `KNOWN` only when evidence directly establishes the relevant cause and there is no material contradiction.

Typical pattern:

```text
direct Stage 6 evidence
+
consistent Stage 5 evidence
+
structurally compatible
```

Stage 5a probability alone can never create `KNOWN`.

---

## LIKELY

The hypothesis has convergent evidence from multiple credible sources, but direct establishment is absent.

Typical pattern:

```text
strong Stage 5 evidence
+
independent Stage 6 evidence
+
structural consistency
+
no material contradiction
```

---

## POSSIBLE

The hypothesis is plausible and supported, but material alternatives or evidence limitations remain.

Typical pattern:

```text
moderate Stage 5 evidence
OR
borrowed evidence
OR
limited observational support
```

A `BORROWED` hypothesis is capped here unless independent native evidence upgrades it.

---

## UNKNOWN

The system cannot responsibly determine whether the hypothesis is true.

Reasons may include:

```text
NO_EVIDENCE
INSUFFICIENT_EVIDENCE
CONFLICTING_EVIDENCE
NON_IDENTIFIABLE
LIMITED_HISTORY
```

The public confidence bucket remains:

```text
UNKNOWN
```

while the internal reason is preserved.

---

# 25. Confidence Must Not Be a Single Weighted Equation

Do not implement:

```text
confidence =
0.4 * stage5_score
+ 0.3 * stage6_score
+ 0.2 * DAG_score
+ 0.1 * contribution
```

That would be arbitrary precision disguised as mathematics.

Instead:

```text
evidence facts
      ↓
deterministic resolution rules
      ↓
confidence bucket
```

Later, if labeled investigations become available, the rule engine can be calibrated or replaced by a learned resolver.

---

# 26. Ranking Model

All candidates are retained when they satisfy the minimum candidate policy.

They are ordered by an interpretable ranking hierarchy.

Recommended ordering:

```text
1. Confidence bucket
2. Strength of independent evidence
3. Analytical support
4. Movement contribution
5. Structural consistency
6. Contradiction burden
```

Conceptually:

```text
KNOWN
  ↓
LIKELY
  ↓
POSSIBLE
  ↓
UNKNOWN
```

Within a bucket:

```text
more independent evidence
→ higher

stronger analytical support
→ higher

larger validated 5b contribution
→ higher

strong contradiction
→ lower
```

No single arbitrary numerical score is required.

---

# 27. Ranking Ties

If two hypotheses remain genuinely indistinguishable:

```text
same confidence
similar evidence
similar analytical support
```

do not fabricate a winner.

They receive the same ranking tier/order group.

Example:

```text
rank = 1
rank_group = A

rank = 1
rank_group = A
```

This is preferable to meaningless decimal differences.

---

# 28. Abstention

Stage 7 returns:

```text
ABSTAIN = true
```

when no hypothesis reaches the minimum defensibility requirement.

Typical triggers:

```text
all hypotheses = UNKNOWN
```

or:

```text
top candidates have unresolved contradictory evidence
```

or:

```text
only weak/borrowed evidence exists
```

or:

```text
5b non-identifiability leaves the candidate mechanism unresolved
```

The ranked candidates are still emitted so downstream stages know what was considered.

---

# 29. Stage 5b Joint Handling

This is a hard boundary.

If Stage 5b emits:

```text
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

Stage 7 emits:

```text
Hypothesis:
product_outage + marketing_cut

identifiability:
NON_IDENTIFIABLE_JOINT
```

It must not emit:

```text
product_outage = 41%
marketing_cut = 24%
```

Those numbers would be fabricated.

Stage 7 may use Stage 6 evidence to increase or decrease confidence in the **joint hypothesis**, but it cannot break the 5b identifiability constraint.

---

# 30. Stage 5c Borrowed Handling

If:

```text
confidence_tier = BORROWED
```

then:

```text
max_confidence = POSSIBLE
```

unless independent native evidence exists.

Example:

```text
5c:
product_outage
borrowed_percentile = 0.94
```

Output:

```text
POSSIBLE
```

not:

```text
LIKELY
```

If Stage 6 subsequently provides direct outage evidence:

```text
BORROWED restriction removed
```

and normal evidence resolution applies.

---

# 31. Recommended Internal Data Model

```python
@dataclass
class EvidenceReference:
    evidence_id: str
    source_type: str
    direction: str
    strength: str
    independent_group_id: str | None
    freshness: str
    provenance_status: str


@dataclass
class AnalyticalEvidence:
    stage5a_probability: float | None
    stage5b_contribution: float | None
    stage5b_share: float | None
    stage5b_identifiability: str | None
    stage5c_borrowed_percentile: float | None
    stage5c_is_borrowed: bool


@dataclass
class StructuralEvidence:
    direction_consistent: bool | None
    timing_consistent: bool | None
    dependency_consistent: bool | None
    relationship_type: str | None


@dataclass
class HypothesisResolution:
    hypothesis_id: str
    member_causes: list[str]
    hypothesis_type: str

    analytical_evidence: AnalyticalEvidence
    supporting_evidence: list[EvidenceReference]
    contradicting_evidence: list[EvidenceReference]
    neutral_evidence: list[EvidenceReference]

    structural_evidence: StructuralEvidence

    confidence_bucket: str
    confidence_reason_codes: list[str]

    contradiction_status: str
    contradiction_reason_codes: list[str]

    evidence_count: int
    independent_source_count: int
    independent_entity_count: int

    identifiability: str
    rank: int | None
    rank_group: str | None
```

---

# 32. Public Output Contract

```python
@dataclass
class RankedHypothesis:
    hypothesis_id: str
    member_causes: list[str]
    hypothesis_type: str

    rank: int
    rank_group: str

    confidence_bucket: str
    confidence_reason_codes: list[str]

    analytical_support: dict
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]

    evidence_count: int
    independent_source_count: int
    independent_entity_count: int

    structural_support: dict

    contradiction_status: str
    contradiction_reason_codes: list[str]

    identifiability: str
    borrowed: bool


@dataclass
class Stage7Result:
    cluster_id: str
    window_start_day_offset: int
    window_end_day_offset: int

    hypotheses: list[RankedHypothesis]

    abstained: bool
    abstention_reason_codes: list[str]

    resolver_version: str
```

---

# 33. Output Example — Clean Case

```json
{
  "cluster_id": "cluster_17",
  "window_start_day_offset": 72,
  "window_end_day_offset": 94,

  "hypotheses": [
    {
      "hypothesis_id": "H1",
      "member_causes": ["product_outage"],
      "hypothesis_type": "SINGLE",
      "rank": 1,
      "rank_group": "A",
      "confidence_bucket": "LIKELY",

      "confidence_reason_codes": [
        "STRONG_ANALYTICAL_SUPPORT",
        "DIRECT_OBSERVATIONAL_SUPPORT",
        "STRUCTURAL_TIMING_CONSISTENCY"
      ],

      "analytical_support": {
        "stage5a_probability": 0.70,
        "stage5b_share": 0.62
      },

      "supporting_evidence_ids": [
        "E12",
        "E19",
        "E24"
      ],

      "contradicting_evidence_ids": [],

      "evidence_count": 3,
      "independent_source_count": 2,
      "independent_entity_count": 3,

      "structural_support": {
        "direction_consistent": true,
        "timing_consistent": true,
        "dependency_consistent": true
      },

      "contradiction_status": "NONE",
      "contradiction_reason_codes": [],

      "identifiability": "IDENTIFIED",
      "borrowed": false
    }
  ],

  "abstained": false,
  "abstention_reason_codes": [],
  "resolver_version": "stage7-resolver-v1"
}
```

---

# 34. Output Example — Confounded Case

```json
{
  "hypothesis_id": "H1",
  "member_causes": [
    "product_outage",
    "marketing_cut"
  ],
  "hypothesis_type": "COMPOUND",

  "rank": 1,
  "rank_group": "A",

  "confidence_bucket": "LIKELY",

  "confidence_reason_codes": [
    "NON_IDENTIFIABLE_JOINT_SUPPORT",
    "STRONG_ANALYTICAL_SUPPORT",
    "DIRECT_OBSERVATIONAL_SUPPORT"
  ],

  "analytical_support": {
    "stage5a_probabilities": {
      "product_outage": 0.42,
      "marketing_cut": 0.38
    },
    "stage5b_share": 0.65
  },

  "identifiability": "NON_IDENTIFIABLE_JOINT",
  "borrowed": false
}
```

No member-level split is present.

---

# 35. Output Example — Borrowed Case

```json
{
  "hypothesis_id": "H3",
  "member_causes": ["product_outage"],
  "hypothesis_type": "SINGLE",

  "rank": 3,

  "confidence_bucket": "POSSIBLE",

  "confidence_reason_codes": [
    "BORROWED_ANALOG_SUPPORT",
    "LIMITED_HISTORY"
  ],

  "analytical_support": {
    "stage5c_borrowed_percentile": 0.91
  },

  "identifiability": "IDENTIFIED",
  "borrowed": true
}
```

It cannot become `LIKELY` from the borrowed signal alone.

---

# 36. Output Example — Contradicted Hypothesis

```json
{
  "hypothesis_id": "H2",
  "member_causes": ["marketing_cut"],
  "hypothesis_type": "SINGLE",

  "rank": 2,

  "confidence_bucket": "POSSIBLE",

  "confidence_reason_codes": [
    "ANALYTICAL_SUPPORT",
    "CONTRADICTED_BY_OBSERVATIONAL_EVIDENCE"
  ],

  "contradiction_status": "PRESENT",

  "contradiction_reason_codes": [
    "DIRECT_BUDGET_RECORD_CONTRADICTION"
  ]
}
```

The hypothesis remains visible but is downgraded and explicitly flagged.

---

# 37. No Narrative Generation in Stage 7

Stage 7 should emit structured reason codes.

Examples:

```text
HIGH_CLASSIFIER_SUPPORT
HIGH_MOVEMENT_CONTRIBUTION
DIRECT_OBSERVATIONAL_SUPPORT
MULTIPLE_INDEPENDENT_SOURCES
EXPECTED_DIRECTION
EXPECTED_TEMPORAL_ORDER
BORROWED_ANALOG_SUPPORT
CONTRADICTED_BY_OBSERVATIONAL_EVIDENCE
NON_IDENTIFIABLE_JOINT_SUPPORT
INSUFFICIENT_EVIDENCE
CONFLICTING_EVIDENCE
```

A later presentation layer may turn these into human-readable language.

Stage 7 itself should not become a narrative-generation service.

---

# 38. Module Architecture

Recommended tree:

```text
pipeline/stage07_hypothesis_debate/
│
├── README.md
├── requirements.txt
│
├── models.py
├── cause_config.py
│
├── input_validator.py
├── candidate_assembler.py
├── hypothesis_builder.py
│
├── evidence/
│   ├── __init__.py
│   ├── analytical.py
│   ├── observational.py
│   ├── structural.py
│   ├── independence.py
│   └── quality.py
│
├── resolution/
│   ├── __init__.py
│   ├── support_resolver.py
│   ├── contradiction_resolver.py
│   ├── confidence_resolver.py
│   └── abstention.py
│
├── ranking/
│   ├── __init__.py
│   └── ranker.py
│
├── output_schema.py
├── stage7.py
│
└── test_stage7.py
```

---

# 39. Module Responsibilities

## `models.py`

Owns all internal and public dataclasses.

No reasoning logic.

---

## `cause_config.py`

Owns:

```text
CAUSE_FAMILIES
allowed compound relationships
dependency rules
candidate probability floor
confidence policies
abstention policies
```

All declared configuration belongs here.

---

## `input_validator.py`

Checks:

```text
cluster/window consistency
cause vocabulary
5b joint integrity
5c borrowed integrity
required Stage 6 fields
```

---

## `candidate_assembler.py`

Collects candidate causes from:

```text
5a
5b
5c
declared structural combinations
```

and deduplicates them.

---

## `hypothesis_builder.py`

Constructs:

```text
single hypotheses
compound hypotheses
5b joint hypotheses
```

It is the only place allowed to create hypothesis objects.

---

## `evidence/analytical.py`

Converts Stage 5 outputs into structured analytical evidence.

---

## `evidence/observational.py`

Maps Stage 6 evidence to existing hypotheses.

No new causes may be created here.

---

## `evidence/structural.py`

Evaluates:

```text
direction
timing
dependency
DAG consistency
```

---

## `evidence/independence.py`

Groups evidence by provenance and computes:

```text
total count
independent source count
independent entity count
```

---

## `evidence/quality.py`

Produces categorical quality assessments.

---

## `support_resolver.py`

Determines:

```text
support level
support reason codes
```

without producing final confidence.

---

## `contradiction_resolver.py`

Determines:

```text
contradiction status
contradiction strength
downgrade/rejection action
```

---

## `confidence_resolver.py`

Combines the structured evidence states using the deterministic rule matrix.

This module owns the semantics of:

```text
KNOWN
LIKELY
POSSIBLE
UNKNOWN
```

---

## `abstention.py`

Determines whether Stage 7 can responsibly rank a leading hypothesis.

---

## `ranker.py`

Orders all retained candidates using the declared ranking hierarchy.

No new evidence is generated here.

---

## `output_schema.py`

Validates:

```text
enum-only cause vocabulary
joint-cause integrity
borrowed cap
required contradiction fields
required evidence provenance
rank consistency
```

---

# 40. Confidence Resolution Rule Matrix

The first implementation should use a rule table rather than scattered `if/else` statements.

Conceptual structure:

```python
RULES = [
    {
        "condition": "direct_evidence + strong_support + no_material_contradiction",
        "bucket": "KNOWN"
    },
    {
        "condition": "independent_convergent_evidence + strong_support",
        "bucket": "LIKELY"
    },
    {
        "condition": "meaningful_support",
        "bucket": "POSSIBLE"
    },
    {
        "condition": "borrowed_only",
        "bucket": "POSSIBLE"
    },
    {
        "condition": "insufficient_or_conflicting",
        "bucket": "UNKNOWN"
    }
]
```

The actual implementation should encode conditions as typed predicates, not free-form strings.

---

# 41. Resolution Precedence

When rules conflict:

```text
1. Hard data-quality / identifiability constraints
2. Direct contradiction
3. Direct observational evidence
4. Multiple independent observational evidence
5. Strong analytical evidence
6. Structural consistency
7. Weak/borrowed evidence
```

This is a precedence order, not a numeric weighting system.

---

# 42. Handling Stage 5a vs Stage 6 Conflict

Example:

```text
Stage 5a:
product_outage = 0.80

Stage 6:
direct evidence says no outage occurred
```

Stage 7 should not blindly preserve the `0.80`.

Result:

```text
product_outage
confidence = UNKNOWN
contradiction = PRESENT
```

Reason:

```text
classifier evidence was contradicted by direct observational evidence
```

The Stage 5a probability remains recorded for auditability.

---

# 43. Handling Stage 5b vs Stage 6 Conflict

Example:

```text
5b:
marketing_cut contribution = 55%

Stage 6:
direct budget record says spend was unchanged
```

Stage 7:

```text
retain hypothesis
flag contradiction
downgrade confidence
```

It does not rewrite the Stage 5b contribution.

Stage 5b's analytical result and Stage 7's evidence judgment remain separate fields.

---

# 44. Handling Compound Hypothesis Evidence

For:

```text
product_outage + marketing_cut
```

Stage 7 evaluates both:

```text
joint existence
```

and:

```text
relationship coherence
```

Example:

```text
outage evidence = strong
marketing-cut evidence = moderate
timing = expected
```

This may support:

```text
compound hypothesis = LIKELY
```

Even if neither individual component could independently be called `KNOWN`.

---

# 45. Ranking All Candidates

The output contains all candidates that survive candidate filtering.

Example:

```text
1. product_outage + marketing_cut — LIKELY
2. competitor_launch              — POSSIBLE
3. inventory_shortage             — POSSIBLE
4. product_outage                 — UNKNOWN
5. seasonal                       — UNKNOWN
```

The user explicitly chose **all candidates with ranked ordering**, rather than truncating to top-1.

A configurable output limit may exist for transport/UI, but the internal Stage 7 result should preserve the complete candidate set.

---

# 46. Seasonal Handling

`seasonal` is not an injected event in the current simulator.

Stage 7 may receive it as a candidate only when an upstream component or structural configuration provides seasonal evidence.

Stage 7 must not invent a seasonal explanation simply because the KPI moved during a calendar period.

Seasonality remains part of normal-variation reasoning upstream, particularly in Stage 2 and the simulator's baseline design.

---

# 47. Unknown Cause Handling

Stage 7 must not create:

```text
UNKNOWN_CAUSE_X
```

as an invented cause family.

If none of the declared causes is sufficiently supported:

```text
abstained = true
```

with:

```text
abstention_reason = NO_DEFENSIBLE_HYPOTHESIS
```

This preserves the closed cause vocabulary.

---

# 48. Stage 8 Contract Boundary

Stage 7 hands Stage 8:

```text
ranked hypotheses
confidence
support
contradiction
identifiability
evidence provenance
```

Stage 8 is then responsible for:

```text
counterfactual estimation
```

Stage 7 does not answer:

```text
"What would revenue have been without the outage?"
```

It only says:

```text
"The outage is the leading supported hypothesis."
```

and provides the Stage 5b contribution where available.

---

# 49. Testing Architecture

Tests should be organized around reasoning boundaries, not just individual functions.

## 49.1 Candidate tests

- Stage 5a candidate enters candidate set.
- Below-floor Stage 5a candidate does not enter unless independently introduced by an allowed source.
- Stage 5b joint component remains one candidate.
- Illegal arbitrary compound is rejected.
- Allowed compound is constructed.

---

# 50. Evidence Tests

### Support

```text
strong Stage 5 + direct Stage 6
→ strong support
```

### Contradiction

```text
strong analytical evidence + direct contradictory record
→ contradiction present
```

### Independence

```text
10 copied records from one source
→ evidence_count = 10
→ independent_source_count = 1
```

### Structural evidence

```text
expected direction + expected lag
→ structural support
```

---

# 51. Confidence Tests

At minimum:

```text
direct + convergent → KNOWN

multiple independent + strong analytical → LIKELY

meaningful but incomplete → POSSIBLE

borrowed-only → POSSIBLE

no evidence → UNKNOWN

conflicting evidence → UNKNOWN or downgraded according to rule

strong contradiction → downgrade
```

---

# 52. 5b Integrity Tests

Mandatory:

```text
NON_IDENTIFIABLE_JOINT
→ no member-level hypothesis contribution split
```

Also:

```text
member-level fabricated contribution
→ schema rejection
```

This is one of the most important Stage 7 tests.

---

# 53. 5c Integrity Tests

Mandatory:

```text
BORROWED only
→ cannot resolve above POSSIBLE
```

Then:

```text
BORROWED + direct native Stage 6 evidence
→ normal confidence resolution allowed
```

---

# 54. Abstention Tests

Cases:

```text
no candidates
→ abstain
```

```text
all candidates UNKNOWN
→ abstain
```

```text
strong conflicting evidence
→ abstain if no defensible leader remains
```

```text
two candidates tied with unresolved evidence
→ retain tie and potentially abstain
```

---

# 55. End-to-End Test Scenarios

## Scenario A — Clean cause

```text
Stage 5a:
product_outage high

Stage 5b:
product_outage high contribution

Stage 6:
direct outage evidence

Result:
product_outage
LIKELY / KNOWN depending on directness
```

---

## Scenario B — Confounded chain

```text
Stage 5a:
outage ≈ marketing cut

Stage 5b:
NON_IDENTIFIABLE_JOINT

Stage 6:
evidence supports both

Result:
product_outage + marketing_cut
LIKELY

No individual split.
```

---

## Scenario C — Borrowed cold-start

```text
Stage 5c:
borrowed percentile high

Stage 6:
no native evidence

Result:
POSSIBLE
BORROWED=true
```

---

## Scenario D — Classifier contradicted

```text
Stage 5a:
product_outage = 0.85

Stage 6:
direct record says no outage

Result:
UNKNOWN
contradiction=PRESENT
```

---

## Scenario E — Competing explanations

```text
H1:
product_outage
strong analytical support
moderate observational support

H2:
competitor_launch
moderate analytical support
strong observational support
```

Stage 7 should compare evidence and may rank H1/H2 depending on the declared resolution rules.

It must not simply select whichever Stage 5a probability is higher.

---

# 56. Auditability Requirements

Every final hypothesis must be traceable to:

```text
Stage 5a inputs
Stage 5b inputs
Stage 5c inputs
Stage 6 evidence IDs
structural rules
confidence reason codes
contradiction reason codes
resolver version
```

A reviewer should be able to answer:

> Why did Stage 7 rank this hypothesis first?

without reading implementation code.

---

# 57. Versioning

The Stage 7 resolver must expose:

```text
resolver_version
```

because the deterministic rules are part of the analytical behavior.

Changing:

```text
confidence rules
ranking precedence
candidate composition rules
```

is a behavior change and should change the resolver version.

---

# 58. Configuration

Recommended initial configuration:

```yaml
candidate_probability_floor: 0.05

confidence:
  borrowed_max: POSSIBLE

ranking:
  retain_all_candidates: true

abstention:
  require_defensible_candidate: true

compound_hypotheses:
  enabled: true
  require_declared_relationship_or_evidence: true

contradiction:
  retain_and_downgrade_by_default: true
```

Avoid numerical confidence thresholds until there is empirical evidence for them.

---

# 59. Explicit Non-Goals

Stage 7 does not:

```text
❌ perform new anomaly detection
❌ perform dimensional decomposition
❌ discover arbitrary causal relationships
❌ generate arbitrary hypotheses
❌ reinterpret 5a probabilities as contributions
❌ split 5b NON_IDENTIFIABLE components
❌ turn BORROWED evidence into native evidence
❌ perform counterfactual estimation
❌ calculate causal effect
❌ generate recommendations
❌ generate narrative explanations
❌ call an LLM
```

Its job is:

```text
Evidence
   ↓
Constrained hypotheses
   ↓
Support + contradiction
   ↓
Evidence resolution
   ↓
Confidence
   ↓
Ranking
   ↓
Abstention when necessary
```

---

# 60. Implementation Build Order

## Phase 1 — Contracts

1. `models.py`
2. `cause_config.py`
3. `output_schema.py`
4. `input_validator.py`

Validate all Stage 5/6 boundaries first.

---

## Phase 2 — Candidate construction

5. `candidate_assembler.py`
6. `hypothesis_builder.py`

Test:

```text
single causes
compound causes
5b joint components
illegal combinations
```

---

## Phase 3 — Evidence normalization

7. `evidence/analytical.py`
8. `evidence/observational.py`
9. `evidence/structural.py`
10. `evidence/independence.py`
11. `evidence/quality.py`

---

## Phase 4 — Resolution

12. `support_resolver.py`
13. `contradiction_resolver.py`
14. `confidence_resolver.py`
15. `abstention.py`

The confidence resolver should be implemented from a testable rule matrix.

---

## Phase 5 — Ranking

16. `ranker.py`

Test deterministic ordering and ties.

---

## Phase 6 — Orchestration

17. `stage7.py`

Conceptual entry point:

```python
run_stage7(
    stage5a_result,
    stage5b_result,
    stage5c_result,
    stage6_result,
    structural_context
) -> Stage7Result
```

No new analysis should live inside this function.

It only orchestrates modules.

---

# 61. Validation Gate

Stage 7 is ready for integration only when:

```text
[ ] All inputs validate

[ ] Candidate causes come only from declared sources

[ ] Illegal compound hypotheses are rejected

[ ] 5b joint components remain joint

[ ] 5c borrowed cap is enforced

[ ] Stage 6 evidence is traceable by ID

[ ] Evidence independence is represented

[ ] Contradictions are explicitly surfaced

[ ] Stage 5a probabilities are never relabeled as contributions

[ ] Confidence buckets follow deterministic rules

[ ] Ranking is deterministic

[ ] Ties are preserved

[ ] Abstention works

[ ] All candidates are emitted in ranked order

[ ] No narrative/LLM logic exists

[ ] Stage 8 receives a stable machine-readable contract
```

---

# 62. Final Architectural Definition

Stage 7 is best understood as:

```text
                 ANALYTICAL EVIDENCE
                 /        |        \
              5a         5b        5c
               \          |         /
                \         |        /
                 └────┬───┴───────┘
                      │
                OBSERVATIONAL
                   EVIDENCE
                      │
                      ▼
              ┌───────────────┐
              │   HYPOTHESIS  │
              │    DEBATE     │
              └───────┬───────┘
                      │
              support / contradiction
                      │
              structural plausibility
                      │
                      ▼
              EVIDENCE RESOLUTION
                      │
                      ▼
          KNOWN / LIKELY / POSSIBLE / UNKNOWN
                      │
                      ▼
                  RANKING
                      │
                 ┌────┴────┐
                 │         │
              ranked    abstain
              output     if needed
                 │
                 ▼
              Stage 8
```

The key design decision is that **Stage 7 does not manufacture certainty**.

It preserves the distinction between:

```text
classifier belief
movement attribution
borrowed evidence
observational evidence
structural plausibility
```

and only then resolves them into a defensible hypothesis ranking.

That is what prevents Stage 7 from becoming an arbitrary scoring layer sitting between Stage 6 and Stage 8.
