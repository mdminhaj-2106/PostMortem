# Stage 9 — Recommendation Assembly & Action Selection
## Detailed Implementation Architecture — AIC / PS3 BusinessIntelligence.ai

**Status:** Architecture finalized after design interview; implementation-ready  
**Stage:** 9  
**Consumes:** Stage 7 ranked hypotheses, Stage 8 counterfactual impact, Stage 5b/5c context where applicable, Stage 1–4 analytical context, company/action configuration, and Learning & Memory outcomes  
**Produces:** One primary recommendation plus compatible alternatives, with driver → lever → action → expected impact → owner → confidence → monitoring plan  
**LLM usage:** None  
**Training:** None

---

# 1. Purpose

Stage 9 is the **decision and recommendation assembly layer**.

It answers:

> Given the hypotheses already resolved by Stage 7 and the quantified consequences produced by Stage 8, what should the business do?

Stage 9 does **not** discover causes, re-rank the diagnosis, perform causal inference, or write narrative prose.

The boundary is:

```text
Stage 7
"What do we believe is happening?"
        ↓
Stage 8
"What is the quantified consequence?"
        ↓
Stage 9
"What should we do?"
        ↓
Stage 10
"How should this decision be adapted to the persona?"
        ↓
Stage 11
"How should it be expressed in natural language?"
```

The overall architecture keeps the LLM boundary absolute: only Stage 11 may call an LLM. Any Stage 9 code path that asks an LLM to decide, generate, or rank an action is an architectural violation.

---

# 2. Locked Design Decisions

| Decision | Final choice |
|---|---|
| Optimization | Confidence-aware multi-objective selection |
| Primary output | One primary recommendation |
| Alternatives | Ranked compatible alternatives |
| Action generation | Structured composition, not a declared action library |
| Action construction | Cause → mechanism → lever → atomic action → context binding |
| Lever mapping | Hybrid: declared allowed levers + causal/KPI graph applicability |
| Hypothesis authority | Stage 7 remains authoritative; Stage 9 cannot replace/re-rank diagnoses |
| Feasibility | Capability feasibility + context feasibility |
| Monetary action cost | Explicitly excluded from MVP |
| Effort/time-to-impact | Optional metadata only; never required |
| Historical feedback | Used as historical action-effectiveness evidence |
| Learning | Feedback may affect future action prioritization, not causal diagnosis |
| Compound causes | Supported |
| 5b joint causes | Remain joint; never split |
| Multiple actions | Allowed when independently feasible and non-conflicting |
| Conflicting actions | Compatibility layer prevents simultaneous recommendation |
| Monitoring | Derived from affected KPIs |
| Success criteria | Generated structurally when enough information exists |
| Narrative | Not produced here |
| LLM | None |
| ML training | None |

---

# 3. Architectural Principles

## 3.1 Stage 9 cannot change the diagnosis

Stage 7 owns hypothesis ranking.

Stage 9 may determine:

```text
ACT
INVESTIGATE
MONITOR
DEFER
```

but it may not decide:

```text
"Actually, hypothesis #2 is the real cause."
```

For example:

```text
Stage 7:

H1 product_outage   = LIKELY
H2 competitor       = POSSIBLE
```

Stage 9 may produce:

```text
Primary:
repair product outage

Alternative:
investigate competitor activity
```

It may not silently promote H2 above H1 because H2 has a more attractive action.

This is a hard boundary.

---

## 3.2 Recommendation strength is not diagnosis confidence

Keep these separate:

```text
diagnosis confidence
    = how strongly Stage 7 supports the hypothesis

action feasibility
    = whether the company can execute the action

historical effectiveness
    = whether similar actions worked previously

counterfactual impact
    = estimated business consequence from Stage 8
```

None of these should be collapsed into a fake universal probability.

---

## 3.3 No arbitrary weighted score

Do not implement:

```text
score =
0.4 × impact
+ 0.3 × confidence
+ 0.2 × feasibility
+ 0.1 × history
```

There is no empirical basis for those weights.

Instead:

```text
hard eligibility gates
        ↓
confidence-aware action eligibility
        ↓
multi-objective comparison
        ↓
compatibility resolution
        ↓
primary + alternatives
```

The comparison retains its dimensions explicitly.

---

# 4. High-Level Architecture

```text
                         Stage 7
                   Ranked hypotheses
                          │
                          ▼
                         Stage 8
                Quantified consequences
                          │
                          ▼
               ┌─────────────────────┐
               │ Stage 9 Input Gate  │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │ Hypothesis Adapter   │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │ Action Candidate     │
               │ Constructor          │
               └──────────┬──────────┘
                          │
              Cause → Mechanism → Lever
                          │
                          ▼
               Atomic Action Builder
                          │
                          ▼
                Context Binding
             ┌────────────┼────────────┐
             ▼            ▼            ▼
          KPI/scope      owner      target
             │            │            │
             └────────────┼────────────┘
                          ▼
               ┌─────────────────────┐
               │ Feasibility Gate    │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │ Historical Outcome   │
               │ Evidence             │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │ Action Compatibility │
               │ / Conflict Resolver  │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │ Multi-objective      │
               │ Selection             │
               └──────────┬──────────┘
                          │
                  ┌───────┴────────┐
                  ▼                ▼
              Primary          Alternatives
                  │                │
                  └───────┬────────┘
                          ▼
               Monitoring / Success
                    Criteria Builder
                          │
                          ▼
                Stage 9 Output
                          │
                          ▼
                       Stage 10
```

---

# 5. Inputs

Stage 9 receives:

```text
Stage7Result
Stage8Result
Stage5bResults
Stage5cResults
CompanyActionContext
LearningMemoryContext
```

Stage 1–4 information is consumed only when required to bind the action to the affected KPI/dimension/scope.

---

# 6. Stage 7 Input

For every ranked hypothesis:

```text
hypothesis_id
member_causes
hypothesis_type
rank
confidence_bucket
confidence_reason_codes
supporting evidence summary
contradicting evidence summary
identifiability
borrowed flag
```

Stage 9 treats Stage 7's ordering as authoritative.

---

# 7. Stage 8 Input

For every eligible hypothesis:

```text
observed KPI
counterfactual KPI
estimated impact
impact interval
impact trajectory
scenario
data confidence
hypothesis reference
mechanism used
```

Stage 9 uses these values to understand the business significance of an action.

Example:

```text
Observed revenue:
₹9.0M

Counterfactual without outage:
₹11.2M

Estimated impact:
₹2.2M

Interval:
₹1.7M–₹2.8M

Confidence:
LIKELY
```

Stage 9 does not recompute this.

---

# 8. Stage 5b Context

Stage 5b is relevant when the diagnosis contains a contribution decomposition.

Example:

```text
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

Stage 9 must preserve this as:

```text
one joint driver
```

and construct an appropriate joint action.

It must never create:

```text
outage impact = ₹1.5M
marketing impact = ₹0.9M
```

unless Stage 5b explicitly established those quantities.

---

# 9. Stage 5c Context

A `BORROWED` diagnosis remains marked as borrowed.

Stage 9 may construct an action around it, but must preserve:

```text
diagnosis_confidence = POSSIBLE
confidence_origin = BORROWED
```

A borrowed diagnosis does not become stronger merely because the resulting action is obvious.

---

# 10. Input Eligibility Gate

For each hypothesis:

```text
Stage 7 abstained?
    → Stage 9 does not recommend ACT

Hypothesis UNKNOWN?
    → no direct causal action unless explicit policy permits investigation

No Stage 8 quantitative basis?
    → action may still be constructed,
       but impact must be UNAVAILABLE

No valid action mechanism?
    → INVESTIGATE / MONITOR / no recommendation

Invalid upstream contract?
    → fail loudly
```

The critical distinction is:

> **A diagnosis can be actionable without having a quantified counterfactual, but Stage 9 must never invent an impact number.**

---

# 11. Decision Status

Stage 9 should operate with a small fixed action-intent vocabulary:

```text
ACT
INVESTIGATE
MONITOR
DEFER
```

`ABSTAIN` is a pipeline-level outcome when no defensible recommendation can be produced.

Recommended semantics:

### ACT

There is a sufficiently credible diagnosis, a valid action mechanism, and sufficient feasibility.

### INVESTIGATE

The issue is material enough to warrant additional investigation, but evidence or action confidence is insufficient for direct intervention.

### MONITOR

The issue is real or plausible, but the expected consequence or evidence does not justify immediate intervention.

### DEFER

The action is valid but should not be selected now because another compatible action has priority or the relevant prerequisite is not currently satisfied.

### ABSTAIN

No recommendation can be defended.

---

# 12. Action Construction — Core Design

The action is **constructed**, not retrieved from a canned action library.

The pipeline is:

```text
CAUSE
  ↓
MECHANISM
  ↓
LEVER
  ↓
ATOMIC ACTION
  ↓
CONTEXT BINDING
  ↓
CONCRETE ACTION
```

Example:

```text
Cause:
product_outage

Mechanism:
product reliability degradation

Lever:
restore product reliability

Atomic action:
REPAIR

Context:
Product A
North
VIP

Concrete action:
repair Product A's affected reliability issue
within the affected scope
```

The internal object remains structured; prose is Stage 11's responsibility.

---

# 13. Cause → Mechanism Mapping

The mechanism identifies **how the cause affects the business**.

Example:

```yaml
product_outage:
  mechanism: reliability_degradation

inventory_shortage:
  mechanism: product_unavailability

marketing_cut:
  mechanism: reduced_acquisition

pricing_change:
  mechanism: price_sensitivity
```

These mappings are declared.

Stage 9 does not infer new causal mechanisms from free text.

---

# 14. Mechanism → Lever Mapping

A mechanism can expose multiple legitimate business levers.

Example:

```yaml
reliability_degradation:
  allowed_levers:
    - restore_reliability
    - reduce_failure_rate
    - incident_remediation
    - investigate_root_failure
```

This is intentionally broader than a single action.

The causal/KPI graph then determines which lever is applicable to the current context.

---

# 15. Hybrid Lever Selection

Lever selection combines:

### Declared allowed levers

The cause/mechanism configuration defines what is permitted.

### Structural applicability

The KPI graph and investigation context determine what is relevant.

Example:

```text
Revenue
  ↓
Orders
  ↓
Conversion
```

If conversion is the affected intermediate KPI:

```text
restore_conversion
```

is applicable.

If inventory availability is the affected mechanism:

```text
restore_inventory
```

is applicable.

A lever that has no structural connection to the observed problem should not be selected.

---

# 16. Atomic Action Primitives

The MVP can use a small controlled vocabulary:

```text
RESTORE
REPAIR
REPLENISH
ROLLBACK
INCREASE
DECREASE
REALLOCATE
INVESTIGATE
MONITOR
```

These are **operations**, not finished recommendations.

Example:

```text
REPLENISH
target = Product A
scope = North
```

becomes the structured action.

The vocabulary is intentionally small and extensible.

---

# 17. Context Binding

Every concrete action should bind as much known context as possible:

```text
KPI
product
region
segment
channel, if applicable
time/window
cause/hypothesis
```

Example:

```json
{
  "action_type": "REPAIR",
  "target": {
    "product": "Product A",
    "region": "North",
    "segment": "VIP"
  },
  "affected_kpis": [
    "revenue",
    "orders",
    "conversion"
  ]
}
```

Stage 9 should not broaden:

```text
North
```

into:

```text
Global
```

unless the action's mechanism explicitly requires global scope.

---

# 18. Scope Selection

The default principle is:

> **Act at the smallest validated scope that covers the diagnosed problem.**

If the evidence says:

```text
Product A
North
VIP
```

the default action should target that scope.

A global action may be selected only when:

```text
the mechanism is global
OR
the configured capability requires global execution
OR
the available evidence indicates broader impact
```

This prevents unnecessarily broad recommendations.

---

# 19. Owner Assignment

Owner resolution is hybrid.

Priority:

```text
1. Action-specific declared owner
2. Lever-specific declared owner
3. Cause/mechanism default owner
```

Example:

```yaml
restore_reliability:
  default_owner: engineering

restore_campaign:
  default_owner: marketing
```

The action object can contain:

```text
primary_owner
secondary_owners[]
```

Multiple owners are permitted.

---

# 20. Joint-Cause Ownership

For:

```text
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

Stage 9 may produce:

```text
primary_owner:
engineering

secondary_owners:
marketing
```

or:

```text
owners:
[engineering, marketing]
```

depending on the actual action composition.

The owner assignment must not imply that the joint causal contribution has been numerically split.

---

# 21. Feasibility

Feasibility has two components.

```text
FEASIBILITY =
    capability feasibility
    +
    context feasibility
```

---

## 21.1 Capability feasibility

Does the company have the capability to execute the action?

Example:

```yaml
capabilities:
  engineering:
    available: true

  marketing:
    available: true

  supply_chain:
    available: true
```

This is company configuration.

It is not requested from the user on every run.

---

## 21.2 Context feasibility

Does the action make sense for the specific diagnosed context?

Example:

```text
Affected:
Product A / North

Candidate:
replenish Product B / South
```

The action is structurally irrelevant and should fail context feasibility.

---

# 22. Why Monetary Cost Is Excluded

The MVP deliberately does **not** require action cost.

Cost is highly context-dependent:

```text
same action
+
different product
+
different region
+
different scale
+
different company state
=
different cost
```

Requesting this information from the user for every recommendation creates poor UX.

Hard-coding cost values creates false precision.

Therefore:

```text
No action-cost score
No user cost questionnaire
No fabricated ROI
```

Cost can be added later as an external business-system input without changing the core Stage 9 architecture.

---

# 23. Optional Effort and Time Metadata

Unlike monetary cost, some actions may have stable operational metadata:

```text
effort = LOW / MEDIUM / HIGH

time_to_impact_days = N
```

These fields are optional.

If unavailable:

```text
effort = UNKNOWN
time_to_impact = UNKNOWN
```

The system does not guess.

---

# 24. Historical Action Effectiveness

Learning & Memory supplies historical outcomes.

Example:

```json
{
  "action_signature": "REPAIR:product_reliability",
  "target_type": "product",
  "historical_attempts": 8,
  "successful_outcomes": 6,
  "failed_outcomes": 2
}
```

Stage 9 uses this as:

```text
historical_action_effectiveness
```

It does not treat it as proof of causality.

---

# 25. What Historical Feedback Can Change

Historical feedback may influence:

```text
action preference
action confidence
feasibility assessment
alternative ordering
```

It may not change:

```text
Stage 7 hypothesis confidence
cause ranking
causal attribution
```

Example:

```text
Stage 7:
product_outage = LIKELY

Historical:
repair action worked 6/8 times
```

→ stronger action preference.

But:

```text
Historical repair worked 6/8 times
```

cannot turn:

```text
competitor_launch = POSSIBLE
```

into:

```text
competitor_launch = LIKELY
```

---

# 26. Historical Feedback Requirements

Learning Memory should retain:

```text
recommendation_id
action_signature
target
timestamp
owner
execution_status
expected_impact
observed_post_action_KPI
success_status
```

This creates a feedback loop:

```text
Recommendation
      ↓
Action executed
      ↓
Outcome observed
      ↓
Success evaluated
      ↓
Learning Memory
      ↓
Future Stage 9
```

No model training is required for the MVP.

---

# 27. Action Effectiveness Evaluation

When sufficient historical observations exist:

```text
SUCCESS
PARTIAL
FAILED
UNKNOWN
```

should be stored.

Stage 9 can use the distribution as structured evidence.

Example:

```text
SUCCESS = 6
PARTIAL = 1
FAILED = 1
```

This is stronger than an unqualified:

```text
"worked before"
```

---

# 28. Candidate Action Generation

For each Stage 7 hypothesis:

```text
1. Read hypothesis causes
2. Resolve mechanism
3. Retrieve allowed levers
4. Check structural applicability
5. Instantiate atomic action
6. Bind affected scope
7. Resolve owner
8. Validate feasibility
9. Attach Stage 8 impact
10. Attach historical effectiveness
```

The result is an `ActionCandidate`.

---

# 29. Action Candidate Internal Model

Recommended structure:

```python
@dataclass
class ActionCandidate:
    action_id: str

    hypothesis_id: str

    driver: list[str]
    mechanism: list[str]
    lever: str

    action_type: str
    action_parameters: dict

    affected_kpis: list[str]
    target_scope: dict

    primary_owner: str | None
    secondary_owners: list[str]

    decision_intent: str

    diagnosis_confidence: str

    expected_impact: float | None
    impact_lower: float | None
    impact_upper: float | None

    historical_effectiveness: dict | None

    feasibility: str
    feasibility_reasons: list[str]

    effort: str | None
    time_to_impact_days: int | None

    evidence_refs: list[str]
    provenance: dict
```

---

# 30. Action Eligibility Gates

An action can proceed toward `ACT` only when:

```text
hypothesis confidence is sufficient
AND
valid action mechanism exists
AND
capability feasibility = FEASIBLE
AND
context feasibility = FEASIBLE
AND
no hard contradiction blocks action
```

If quantitative impact is unavailable:

```text
ACT may still be possible
```

but:

```text
expected_impact = UNAVAILABLE
```

must remain explicit.

---

# 31. Confidence-Aware Action Policy

Recommended policy:

```text
KNOWN
→ ACT allowed

LIKELY
→ ACT allowed

POSSIBLE
→ normally INVESTIGATE or MONITOR
   unless explicit action policy permits low-regret ACT

UNKNOWN
→ no causal ACT
→ INVESTIGATE / MONITOR
```

The exact policy is configuration-driven.

The important principle is that:

```text
POSSIBLE
```

does not automatically mean:

```text
do nothing
```

nor:

```text
take aggressive action
```

The action policy determines the appropriate response.

---

# 32. Low-Regret Actions

A `POSSIBLE` hypothesis may still yield an `ACT` recommendation when the action is explicitly classified as low-regret.

Example:

```text
Hypothesis:
inventory_shortage = POSSIBLE

Action:
check/reconcile inventory
```

This is fundamentally different from:

```text
Hypothesis:
inventory_shortage = POSSIBLE

Action:
spend ₹10M expanding inventory
```

The latter would require much stronger evidence.

Since monetary cost is excluded, the system should rely on an explicit action-risk classification:

```text
LOW_REGRET
HIGH_COMMITMENT
```

rather than inventing a cost.

---

# 33. Multi-Objective Action Comparison

Eligible actions are compared on separate dimensions:

```text
1. Diagnosis confidence
2. Counterfactual impact magnitude
3. Feasibility
4. Historical effectiveness
5. Effort, if known
6. Time-to-impact, if known
7. Contradiction burden
```

Do not collapse them into a universal scalar.

The selection process is:

```text
remove dominated actions
        ↓
respect confidence policy
        ↓
respect feasibility
        ↓
respect compatibility
        ↓
select primary
        ↓
retain strong alternatives
```

---

# 34. Dominance

Action A dominates action B if A is:

```text
no worse on all relevant dimensions
AND
strictly better on at least one
```

Example:

```text
A:
LIKELY
₹3M
FEASIBLE
HIGH historical effectiveness

B:
POSSIBLE
₹2M
FEASIBLE
LOW historical effectiveness
```

A dominates B.

B need not remain an alternative.

---

# 35. Non-Dominated Alternatives

Example:

```text
A:
LIKELY
₹3M
high effort

B:
LIKELY
₹2.5M
low effort

C:
POSSIBLE
₹5M
low historical effectiveness
```

None may be fully dominated.

Stage 9 can return:

```text
Primary:
A

Alternative:
B

Secondary alternative:
C
```

with explicit trade-offs.

---

# 36. Primary Recommendation Selection

The primary recommendation should be selected through a deterministic ordering:

```text
1. Passes action eligibility
2. Passes confidence policy
3. Feasible
4. Non-dominated
5. Stronger diagnosis confidence
6. Stronger counterfactual impact
7. Better historical effectiveness
8. Better known execution characteristics
9. Stable deterministic tie-breaker
```

This is a hierarchy, not an arbitrary weighted score.

---

# 37. Stable Tie-Breaking

If two candidates are genuinely equivalent:

```text
same confidence
same impact class
same feasibility
same historical effectiveness
```

do not manufacture a meaningful decimal distinction.

Use a deterministic stable ordering such as:

```text
Stage 7 hypothesis rank
then action_id
```

This guarantees reproducibility.

---

# 38. Action Compatibility

Stage 9 must detect conflicts between actions.

Each action carries semantic attributes such as:

```text
action_domain
target
operation
direction
```

Example:

```json
{
  "operation": "PRICE_CHANGE",
  "direction": "DECREASE",
  "target": "Product A"
}
```

versus:

```json
{
  "operation": "PRICE_CHANGE",
  "direction": "INCREASE",
  "target": "Product A"
}
```

→ conflict.

---

# 39. Compatible Actions

Compatible actions may be recommended together.

Example:

```text
repair Product A
+
increase Product A promotion
```

if the configured action semantics indicate no conflict.

The result can contain:

```text
primary:
repair Product A

parallel:
increase promotion
```

The second action remains tied to its own hypothesis.

---

# 40. Conflict Resolution

When actions conflict:

```text
A → decrease price
B → increase price
```

Stage 9 must not recommend both.

Resolution follows:

```text
higher Stage 7 hypothesis rank
→ stronger confidence
→ stronger impact
→ better feasibility
→ historical effectiveness
```

The losing action becomes:

```text
alternative
```

or:

```text
DEFER
```

rather than being silently discarded.

---

# 41. Compound Actions

A compound hypothesis can produce a compound action.

Example:

```text
Hypothesis:
product_outage + marketing_cut

Action:
joint remediation
```

or:

```text
Action 1:
repair Product A

Action 2:
restore affected marketing activity
```

If the causes are independently actionable and the actions do not conflict, both can be retained.

---

# 42. Joint Cause Constraint

For:

```text
NON_IDENTIFIABLE_JOINT
```

Stage 9 may recommend:

```text
joint investigation
joint remediation
coordinated action
```

but must not claim:

```text
engineering owns 70%
marketing owns 30%
```

unless that split came from an upstream identifiable result.

---

# 43. Recommendation Intent Resolution

For each action:

```text
confidence
+
feasibility
+
impact
+
action risk
```

determine:

```text
ACT
INVESTIGATE
MONITOR
DEFER
```

Examples:

```text
LIKELY + FEASIBLE + material impact
→ ACT
```

```text
POSSIBLE + high-regret action
→ INVESTIGATE
```

```text
POSSIBLE + low-regret monitoring action
→ MONITOR / ACT depending on policy
```

```text
VALID ACTION + blocked prerequisite
→ DEFER
```

---

# 44. Monitoring Plan

Monitoring is derived from the affected KPI set.

For every recommendation, Stage 9 should identify:

```text
KPI(s)
expected direction
monitoring horizon, if available
success condition
```

Example:

```json
{
  "kpis": [
    {
      "kpi": "revenue",
      "expected_direction": "UP"
    },
    {
      "kpi": "orders",
      "expected_direction": "UP"
    },
    {
      "kpi": "conversion",
      "expected_direction": "UP"
    }
  ]
}
```

---

# 45. Monitoring Horizon

If the action mechanism supplies a reliable:

```text
time_to_impact
```

Stage 9 can use it.

Otherwise:

```text
monitoring_horizon = NOT_SPECIFIED
```

It must not invent:

```text
"Check after 14 days"
```

without a configured basis.

---

# 46. Success Criteria

When Stage 8 provides a counterfactual trajectory, Stage 9 can construct a structured success criterion.

Example:

```text
Target KPI:
revenue

Expected direction:
UP

Success condition:
observed trajectory moves toward the
counterfactual trajectory after intervention
```

Where an explicit threshold exists in configuration, it may be used:

```text
within configured tolerance of target
```

Otherwise:

```text
success_condition_status = DERIVABLE
```

or:

```text
NOT_DERIVABLE
```

No fake numerical target is invented.

---

# 47. Recommendation Object

Recommended public contract:

```json
{
  "cluster_id": "cluster_2026_08_c17",

  "decision_status": "RECOMMENDATION_AVAILABLE",

  "primary_recommendation": {
    "hypothesis_id": "H1",

    "driver": [
      "product_outage"
    ],

    "mechanism": [
      "reliability_degradation"
    ],

    "lever": "restore_reliability",

    "action": {
      "type": "REPAIR",
      "target": {
        "product": "Product A",
        "region": "North",
        "segment": "VIP"
      }
    },

    "owner": {
      "primary": "engineering",
      "secondary": []
    },

    "decision_intent": "ACT",

    "expected_impact": {
      "value": 2200000,
      "lower": 1700000,
      "upper": 2800000,
      "currency": "INR"
    },

    "confidence": {
      "diagnosis": "LIKELY",
      "impact_data": "MEDIUM"
    },

    "historical_effectiveness": {
      "status": "FAVORABLE",
      "sample_size": 8
    },

    "feasibility": {
      "status": "FEASIBLE",
      "capability": "AVAILABLE",
      "context": "VALID"
    },

    "monitoring_plan": {
      "kpis": [
        {
          "kpi": "revenue",
          "expected_direction": "UP"
        },
        {
          "kpi": "orders",
          "expected_direction": "UP"
        }
      ]
    },

    "success_criteria": {
      "status": "DERIVABLE",
      "basis": "COUNTERFACTUAL_TRAJECTORY"
    }
  },

  "alternatives": [],

  "tradeoffs": [],

  "provenance": {}
}
```

---

# 48. Expected Impact Semantics

Stage 9 exposes both:

```text
counterfactual KPI
```

and:

```text
estimated impact
```

Example:

```text
Observed:
₹9.0M

Counterfactual:
₹11.2M

Estimated impact:
₹2.2M
```

The recommendation should never relabel this as:

```text
guaranteed recovery
```

It remains:

```text
estimated impact
```

---

# 49. Impact Interval

Stage 8's interval is passed through unchanged.

Stage 9 does not narrow it.

Example:

```text
₹1.7M–₹2.8M
```

remains:

```text
₹1.7M–₹2.8M
```

unless a future recommendation-specific uncertainty transformation is explicitly designed.

---

# 50. Trade-Off Representation

Trade-offs are structured, not generated prose.

Examples:

```text
HIGHER_IMPACT
LOWER_CONFIDENCE

HIGHER_CONFIDENCE
LOWER_IMPACT

HIGHER_EFFORT
LOWER_EFFORT

PRIMARY_ACTION_CONFLICT
PARALLEL_ACTION_AVAILABLE
```

Stage 11 later converts these into natural language.

---

# 51. Alternatives

Alternatives should be meaningful, not merely every remaining candidate.

An alternative is retained when:

```text
it is feasible
AND
not dominated
AND
materially different from primary
AND
supported by its own hypothesis
```

Example:

```text
Primary:
repair outage

Alternative:
increase promotion

```

if both are independently defensible.

---

# 52. Recommendation Statuses

Recommended top-level statuses:

```text
RECOMMENDATION_AVAILABLE
INVESTIGATION_RECOMMENDED
MONITORING_RECOMMENDED
NO_DEFENSIBLE_ACTION
```

`NO_DEFENSIBLE_ACTION` is different from an error.

It is a valid analytical result.

---

# 53. No-Action Example

```text
Stage 7:
competitor_launch = POSSIBLE

Stage 8:
impact unavailable

No validated intervention mechanism

→

decision_status:
INVESTIGATION_RECOMMENDED

primary intent:
INVESTIGATE
```

The system does not invent:

```text
"Launch a discount campaign"
```

---

# 54. Data-Quality Propagation

Stage 9 retains Stage 8's data confidence.

Example:

```text
impact_data = LOW
```

should not become:

```text
high-confidence recommendation
```

The action can still be recommended if the action policy permits it, but the recommendation retains the uncertainty.

---

# 55. Borrowed Evidence Propagation

For Stage 5c:

```text
confidence_origin = BORROWED
```

must survive into:

```text
primary_recommendation.confidence
```

and:

```text
provenance
```

Stage 9 cannot upgrade a borrowed diagnosis to `LIKELY` simply because it produced a feasible action.

Independent native evidence from Stage 7 is required for an upgrade.

---

# 56. Provenance

Every recommendation should be traceable to:

```text
hypothesis_id
Stage 7 result
Stage 8 result
mechanism_id
lever configuration
action construction rule
owner configuration
feasibility configuration
historical memory references
monitoring derivation
```

This is essential for debugging and demo auditability.

---

# 57. Configuration

Recommended structure:

```text
stage09/
├── config/
│   ├── cause_mechanisms.yaml
│   ├── mechanism_levers.yaml
│   ├── action_primitives.yaml
│   ├── action_compatibility.yaml
│   ├── owner_mapping.yaml
│   ├── company_capabilities.yaml
│   ├── action_policies.yaml
│   └── monitoring.yaml
```

---

# 58. Example Configuration

```yaml
causes:

  product_outage:
    mechanism: reliability_degradation

mechanisms:

  reliability_degradation:
    allowed_levers:
      - restore_reliability
      - investigate_root_failure

levers:

  restore_reliability:
    allowed_actions:
      - REPAIR
      - RESTORE
    default_owner: engineering

  investigate_root_failure:
    allowed_actions:
      - INVESTIGATE
    default_owner: engineering
```

---

# 59. Action Policy Configuration

```yaml
confidence_policy:

  KNOWN:
    allowed_intents:
      - ACT
      - INVESTIGATE
      - MONITOR

  LIKELY:
    allowed_intents:
      - ACT
      - INVESTIGATE
      - MONITOR

  POSSIBLE:
    default_intent: INVESTIGATE
    low_regret_override: MONITOR

  UNKNOWN:
    default_intent: INVESTIGATE
```

The configuration controls policy; it does not change Stage 7 confidence.

---

# 60. Company Capability Configuration

```yaml
company:

  capabilities:

    engineering:
      available: true

    marketing:
      available: true

    supply_chain:
      available: true
```

This is deliberately small for the prototype.

It can later be replaced with an external operational-system adapter.

---

# 61. Action Semantic Configuration

```yaml
actions:

  PRICE_INCREASE:
    operation: PRICE_CHANGE
    direction: INCREASE

  PRICE_DECREASE:
    operation: PRICE_CHANGE
    direction: DECREASE

  REPAIR:
    operation: REMEDIATION

  REPLENISH:
    operation: INVENTORY_CHANGE
```

This provides the data needed for compatibility checking.

---

# 62. Compatibility Rules

```yaml
compatibility:

  PRICE_INCREASE:
    conflicts_with:
      - PRICE_DECREASE

  PRICE_DECREASE:
    conflicts_with:
      - PRICE_INCREASE
```

More complex conflicts can include target overlap:

```text
same operation
+
same target
+
opposite direction
```

---

# 63. Learning & Memory Adapter

Stage 9 should use an adapter:

```python
class ActionOutcomeRepository:

    def get_history(
        self,
        action_signature,
        target_context
    ) -> ActionHistory:
        ...
```

This keeps Stage 9 independent of the storage implementation.

If Learning & Memory is not available:

```text
historical_effectiveness = UNKNOWN
```

The recommendation system still works.

---

# 64. Main Runtime API

Recommended:

```python
def run_stage9(
    stage7_result,
    stage8_result,
    stage5b_results=None,
    stage5c_results=None,
    company_context=None,
    learning_memory=None
) -> Stage9Result:
    ...
```

Pure candidate construction should also be exposed:

```python
def construct_action_candidates(
    hypotheses,
    impact_results,
    action_config,
    company_context,
    historical_context
) -> list[ActionCandidate]:
    ...
```

And deterministic selection:

```python
def select_recommendations(
    candidates
) -> RecommendationSet:
    ...
```

This keeps business logic unit-testable without database dependencies.

---

# 65. Module Breakdown

Recommended implementation:

```text
stage09_recommendation_assembly/
│
├── config/
│   ├── cause_mechanisms.yaml
│   ├── mechanism_levers.yaml
│   ├── action_primitives.yaml
│   ├── action_compatibility.yaml
│   ├── owner_mapping.yaml
│   ├── company_capabilities.yaml
│   ├── action_policies.yaml
│   └── monitoring.yaml
│
├── models.py
├── input_validator.py
├── hypothesis_adapter.py
│
├── mechanism_resolver.py
├── lever_resolver.py
├── action_builder.py
├── context_binder.py
├── owner_resolver.py
│
├── feasibility/
│   ├── capability.py
│   └── context.py
│
├── historical_effectiveness.py
│
├── compatibility/
│   ├── semantics.py
│   └── conflict_resolver.py
│
├── ranking/
│   ├── eligibility.py
│   ├── dominance.py
│   └── selector.py
│
├── monitoring.py
├── success_criteria.py
├── provenance.py
├── output_schema.py
├── stage9.py
└── test_stage9.py
```

---

# 66. Responsibility of Each Module

## `input_validator.py`

Validates:

```text
Stage 7 schema
Stage 8 schema
cluster/window consistency
hypothesis references
confidence values
joint-cause constraints
```

---

## `hypothesis_adapter.py`

Converts Stage 7 hypotheses into the internal representation.

It does not change ranking.

---

## `mechanism_resolver.py`

Maps:

```text
cause → mechanism
```

using declared configuration.

---

## `lever_resolver.py`

Maps:

```text
mechanism → allowed levers
```

then filters by structural applicability.

---

## `action_builder.py`

Converts:

```text
lever → atomic action
```

and creates the structured action object.

---

## `context_binder.py`

Adds:

```text
product
region
segment
KPI
scope
time
```

---

## `owner_resolver.py`

Determines:

```text
primary owner
secondary owners
```

---

## `feasibility/*`

Checks:

```text
company capability
context validity
```

---

## `historical_effectiveness.py`

Queries Learning & Memory and returns structured action-outcome evidence.

---

## `compatibility/*`

Determines whether candidate actions:

```text
can coexist
conflict
or require deferral
```

---

## `ranking/*`

Implements:

```text
eligibility
dominance
deterministic selection
```

No learned ranking model.

---

## `monitoring.py`

Derives monitoring KPIs and expected directions.

---

## `success_criteria.py`

Builds structured post-action success conditions where derivable.

---

## `provenance.py`

Records all configuration and upstream references used to construct the recommendation.

---

# 67. Runtime Algorithm

```python
def run_stage9(...):

    validate_inputs()

    if stage7_result.abstained:
        return no_defensible_action(
            reason="STAGE7_ABSTAINED"
        )

    hypotheses = adapt_hypotheses(stage7_result)

    candidates = []

    for hypothesis in hypotheses:

        impact = get_stage8_impact(
            hypothesis.hypothesis_id
        )

        mechanisms = resolve_mechanisms(
            hypothesis
        )

        if not mechanisms:
            candidates.append(
                build_investigation_candidate(
                    hypothesis,
                    reason="NO_VALIDATED_MECHANISM"
                )
            )
            continue

        levers = resolve_applicable_levers(
            hypothesis,
            mechanisms
        )

        for lever in levers:

            action = build_action(
                hypothesis,
                lever
            )

            action = bind_context(
                action,
                hypothesis,
                upstream_context
            )

            owner = resolve_owner(action)

            feasibility = evaluate_feasibility(
                action,
                company_context
            )

            history = get_action_history(
                action,
                learning_memory
            )

            candidate = assemble_candidate(
                hypothesis,
                impact,
                action,
                owner,
                feasibility,
                history
            )

            candidate.intent = resolve_intent(
                candidate
            )

            candidates.append(candidate)

    candidates = remove_invalid(candidates)

    candidates = resolve_action_conflicts(
        candidates
    )

    primary, alternatives = select_recommendations(
        candidates
    )

    monitoring = build_monitoring_plan(
        primary,
        impact
    )

    success = build_success_criteria(
        primary,
        impact
    )

    return assemble_stage9_result(
        primary,
        alternatives,
        monitoring,
        success
    )
```

---

# 68. Important: Candidate Generation Does Not Mean Recommendation

The system may generate:

```text
10 candidate actions
```

but return:

```text
1 primary
2 alternatives
```

The candidate set is an internal search space.

It should not leak into the user-facing output unless useful for audit/debugging.

---

# 69. Decision Matrix

A useful deterministic policy table:

| Diagnosis | Mechanism | Feasible | Impact | Default |
|---|---|---|---|---|
| KNOWN | yes | yes | available | ACT |
| LIKELY | yes | yes | available | ACT |
| LIKELY | yes | yes | unavailable | ACT / policy |
| POSSIBLE | yes | yes | high | INVESTIGATE |
| POSSIBLE | yes | yes | low-regret | MONITOR |
| UNKNOWN | yes | yes | any | INVESTIGATE |
| Any | no | — | any | INVESTIGATE / MONITOR |
| Any | yes | no | any | DEFER / INVESTIGATE |

This table is policy, not statistical truth.

---

# 70. Primary + Alternative Example

Input:

```text
H1:
product_outage
LIKELY
impact = ₹2.2M

H2:
competitor_launch
POSSIBLE
impact = ₹3.1M
```

Possible result:

```text
PRIMARY:
repair Product A outage

ALTERNATIVE:
investigate competitor activity
```

The larger H2 impact does not automatically displace H1.

Why?

Because Stage 7 remains authoritative and H2 has weaker diagnostic support.

---

# 71. Parallel Action Example

Input:

```text
H1:
product_outage
LIKELY

H2:
marketing_cut
LIKELY
```

Actions:

```text
repair Product A
restore affected marketing activity
```

If compatible:

```text
PRIMARY:
repair Product A

PARALLEL ALTERNATIVE:
restore affected marketing activity
```

The final output may label the second as:

```text
parallel_action = true
```

rather than implying it is merely a fallback.

---

# 72. Conflicting Action Example

```text
H1:
pricing_change
LIKELY
→ increase price

H2:
pricing_change
POSSIBLE
→ decrease price
```

Compatibility resolver:

```text
CONFLICT
```

Stage 7 order and confidence policy determine the surviving primary.

The losing action becomes:

```text
DEFERRED_ALTERNATIVE
```

rather than being simultaneously recommended.

---

# 73. Joint Cause Example

```text
H1:
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
impact = ₹2.4M
```

Stage 9:

```text
driver:
product_outage + marketing_cut

lever:
joint_recovery

action:
coordinate product remediation and affected
marketing restoration

owners:
engineering + marketing

impact:
₹2.4M

member-level split:
NOT_IDENTIFIABLE
```

This preserves the upstream identifiability constraint.

---

# 74. Cold-Start Example

```text
Stage 5c:
BORROWED

Stage 7:
POSSIBLE

Stage 8:
no validated quantitative intervention
```

Stage 9:

```text
decision_intent:
INVESTIGATE

confidence_origin:
BORROWED

expected_impact:
UNAVAILABLE
```

It does not fabricate an impact.

---

# 75. Monitoring-Only Example

Suppose:

```text
Stage 7:
POSSIBLE

Action:
monitor affected KPI

Action risk:
LOW_REGRET
```

Stage 9 can output:

```text
decision_intent:
MONITOR

monitor:
revenue
conversion
orders

success:
movement stabilizes / returns toward expected trajectory
```

This is a valid recommendation, not an analytical failure.

---

# 76. What Stage 9 Does Not Ask the User

Normal runtime should not ask:

```text
What does this action cost?
Who should execute it?
How many engineers are available?
How much budget do you have?
Should we act globally?
```

Instead:

```text
company configuration
+
action semantics
+
investigation scope
+
Stage 7
+
Stage 8
```

provide what is required.

If information is genuinely unavailable, the system should mark it:

```text
UNKNOWN
```

and adjust the decision.

---

# 77. Error Handling

Hard errors:

```text
invalid Stage 7 schema
invalid Stage 8 schema
cluster mismatch
unknown cause
malformed action configuration
invalid compatibility rule
```

should fail explicitly.

Soft analytical limitations:

```text
no historical action outcome
no impact estimate
unknown effort
unknown time-to-impact
```

should produce structured `UNKNOWN` fields.

---

# 78. Logging

Structured events:

```text
STAGE9_INPUT_VALIDATED
HYPOTHESIS_ADAPTED
MECHANISM_RESOLVED
LEVER_SELECTED
ACTION_CONSTRUCTED
ACTION_CONTEXT_BOUND
FEASIBILITY_EVALUATED
HISTORICAL_EFFECTIVENESS_ATTACHED
ACTION_CONFLICT_DETECTED
ACTION_DOMINATED
PRIMARY_SELECTED
ALTERNATIVE_SELECTED
MONITORING_PLAN_BUILT
SUCCESS_CRITERIA_BUILT
RECOMMENDATION_EMITTED
```

No narrative logging is necessary.

---

# 79. Testing Strategy

Stage 9 needs tests at four levels:

```text
1. Unit
2. Integration
3. Golden-path
4. End-to-end decision evaluation
```

---

# 80. Unit Tests — Action Construction

Test:

```text
cause → mechanism
mechanism → lever
lever → action
action → context
```

Example:

```text
product_outage
→ reliability_degradation
→ restore_reliability
→ REPAIR
→ Product A / North / VIP
```

Assert exact structured output.

---

# 81. Unit Tests — Feasibility

Test:

```text
capability available
→ FEASIBLE

capability unavailable
→ NOT_FEASIBLE

wrong target scope
→ CONTEXT_INVALID
```

---

# 82. Unit Tests — Compatibility

Test:

```text
PRICE_INCREASE + PRICE_DECREASE
→ conflict
```

and:

```text
REPAIR + MARKETING_RESTORE
→ compatible
```

where configuration declares them compatible.

---

# 83. Unit Tests — Confidence Policy

Test:

```text
KNOWN → ACT allowed
LIKELY → ACT allowed
POSSIBLE → INVESTIGATE default
UNKNOWN → INVESTIGATE
```

Also test low-regret overrides.

---

# 84. Unit Tests — Joint Cause

Input:

```text
NON_IDENTIFIABLE_JOINT
```

Assert:

```text
one joint driver
no member contribution split
owners preserved
```

---

# 85. Unit Tests — Borrowed Evidence

Input:

```text
BORROWED
```

Assert:

```text
confidence_origin = BORROWED
```

and that no code path upgrades it independently.

---

# 86. Golden Path

Use the project's canonical example:

```text
revenue decline
North
VIP
Product A
product outage
```

Stage 7:

```text
product_outage = LIKELY
```

Stage 8:

```text
impact = ₹2.2M
```

Stage 9 should produce:

```text
driver:
product_outage

lever:
restore_reliability

action:
REPAIR Product A
within affected scope

owner:
engineering

intent:
ACT

expected impact:
₹2.2M

interval:
₹1.7M–₹2.8M

monitor:
revenue
orders
conversion
```

---

# 87. Primary/Alternative Golden Test

Construct:

```text
H1:
LIKELY
impact = ₹2.2M
repair action

H2:
POSSIBLE
impact = ₹3.0M
promotion action
```

Assert:

```text
H1 remains primary
H2 is alternative
```

This verifies that Stage 9 does not allow raw impact to override Stage 7 diagnosis.

---

# 88. Parallel-Action Golden Test

Construct two hypotheses:

```text
H1:
LIKELY
repair

H2:
LIKELY
marketing restore
```

Assert:

```text
both retained
```

when their actions are compatible.

---

# 89. Conflict Golden Test

Construct:

```text
H1:
LIKELY
price increase

H2:
POSSIBLE
price decrease
```

Assert:

```text
both are not simultaneously recommended
```

and that the Stage 7-preferred candidate wins.

---

# 90. Historical Feedback Test

Provide:

```text
historical attempts = 8
successful = 6
```

Assert:

```text
historical_effectiveness attached
```

Then change history to:

```text
successful = 1
failed = 7
```

and verify that action preference can change **without changing Stage 7 hypothesis confidence**.

---

# 91. Missing Learning Memory Test

Learning Memory unavailable:

```text
historical_effectiveness = UNKNOWN
```

Stage 9 must still produce a valid recommendation if all other requirements are met.

---

# 92. Missing Cost Test

No cost data exists.

Assert:

```text
no error
no fabricated cost
no fabricated ROI
```

Recommendation remains valid.

---

# 93. Missing Stage 8 Impact Test

A hypothesis has:

```text
Stage 7:
LIKELY

Stage 8:
UNAVAILABLE
```

Stage 9 should be able to produce:

```text
ACT / INVESTIGATE
```

according to policy, while:

```text
expected_impact = UNAVAILABLE
```

rather than manufacturing a number.

---

# 94. Monitoring Tests

Given affected KPIs:

```text
revenue
orders
conversion
```

assert:

```text
all three appear in monitoring plan
```

with correct expected directions.

---

# 95. Success Criteria Tests

Where Stage 8 supplies a counterfactual trajectory:

```text
success criteria = DERIVABLE
```

Where it does not:

```text
success criteria = NOT_DERIVABLE
```

No invented thresholds.

---

# 96. Regression / Integrity Tests

The test suite should explicitly verify:

```text
Stage 9 does not import any LLM client
```

and:

```text
Stage 9 never modifies Stage 7 hypothesis ranking
```

and:

```text
Stage 9 never splits 5b NON_IDENTIFIABLE_JOINT
```

and:

```text
Stage 9 never emits monetary action cost
```

unless a future extension explicitly adds it.

---

# 97. Evaluation Metrics

Because Stage 9 is a decision layer, evaluate more than "recommendation sounds good."

## Action validity

Percentage of emitted actions that:

```text
map to valid configured mechanisms
```

## Feasibility accuracy

Whether recommended actions are actually executable in simulator/company context.

## Hypothesis preservation

Percentage of cases where Stage 9 preserves Stage 7's authoritative diagnosis.

Target:

```text
100%
```

for the prototype.

## Conflict precision

Percentage of known conflicting actions correctly prevented from simultaneous recommendation.

## Action selection quality

Compare selected primary action against simulator ground truth where the simulator explicitly knows the best intervention.

## Monitoring completeness

Percentage of recommendations with all affected KPIs represented.

---

# 98. Offline Simulator Evaluation

The simulator can provide stronger evaluation.

For an injected event:

```text
ground_truth_cause
ground_truth_affected_scope
ground_truth_effect
```

compare:

```text
Stage 7 diagnosis
+
Stage 8 impact
+
Stage 9 action
```

against the actual event and available remediation.

This creates a full-chain evaluation:

```text
cause detection
→ impact estimation
→ action selection
```

---

# 99. Action Selection Metric

Where the simulator declares a preferred remediation:

```text
Action Top-1 Accuracy
```

can be measured.

For example:

```text
correct primary action
/
cases with a defined ground-truth remediation
```

Cases without a uniquely correct action should not be scored as failures.

---

# 100. Abstention / Investigation Quality

Measure:

```text
correct INVESTIGATE
correct MONITOR
incorrect forced ACT
```

The architecture should reward appropriate restraint.

A system that always produces an action is not necessarily better.

---

# 101. Build Order

## Step 1 — Finalize configuration vocabulary

Define:

```text
causes
mechanisms
levers
atomic actions
owners
capabilities
compatibility
action policies
```

This is blocking.

---

## Step 2 — Implement internal data models

Create:

```text
ActionCandidate
FeasibilityResult
ActionHistory
Recommendation
RecommendationSet
MonitoringPlan
SuccessCriteria
```

---

## Step 3 — Implement Stage 7/8 adapters

Consume existing contracts without altering semantics.

---

## Step 4 — Implement mechanism resolution

```text
cause → mechanism
```

---

## Step 5 — Implement lever resolution

```text
mechanism → allowed levers
```

plus structural applicability.

---

## Step 6 — Implement action construction

```text
lever → atomic action → context
```

---

## Step 7 — Implement feasibility

Capability + context.

---

## Step 8 — Implement owner resolution

Primary + secondary owners.

---

## Step 9 — Implement Learning Memory adapter

Historical effectiveness only.

---

## Step 10 — Implement compatibility engine

Conflict detection and parallel-action support.

---

## Step 11 — Implement deterministic action selection

Eligibility → dominance → primary → alternatives.

---

## Step 12 — Implement monitoring and success criteria

Derive from affected KPIs and Stage 8 where possible.

---

## Step 13 — Implement provenance and output validation

Every recommendation must be traceable.

---

## Step 14 — Run golden-path and simulator tests

Do not connect Stage 10/11 until Stage 9's structured output is stable.

---

# 102. CLI

Recommended:

```bash
python -m pipeline.stage09_recommendation_assembly.stage9 \
    --episode-id 42
```

Optional:

```bash
--hypothesis-id H1
```

for debugging a specific recommendation path.

Optional:

```bash
--show-candidates
```

for development/debug output.

The production result should still expose only:

```text
primary
alternatives
decision status
monitoring
provenance
```

---

# 103. Database Boundary

Stage 9 should not query raw Layer 1 simulator tables.

It should consume:

```text
Stage 7/8 outputs
+
declared configuration
+
Learning & Memory adapter
```

consistent with the project's rule that downstream stages do not bypass the observed-data boundary.

The architecture's cross-stage import problem is already known to be significant; Stage 9 should use the consolidated package structure if that migration has been completed rather than introducing another `sys.path` bridge.

---

# 104. No LLM Boundary

Stage 9 contains:

```text
NO LLM
NO embedding model
NO generative model
NO training
```

The only language-like material should be:

```text
enum identifiers
structured action labels
configuration keys
```

Stage 11 owns natural-language narration.

---

# 105. Final End-to-End Example

```text
Stage 7
────────────────────────────
Hypothesis:
product_outage

Confidence:
LIKELY

Rank:
1


Stage 8
────────────────────────────
Observed revenue:
₹9.0M

Counterfactual:
₹11.2M

Impact:
₹2.2M

Interval:
₹1.7M–₹2.8M


Stage 9
────────────────────────────
Driver:
product_outage

Mechanism:
reliability_degradation

Lever:
restore_reliability

Action:
REPAIR Product A
scope = North / VIP

Owner:
Engineering

Intent:
ACT

Diagnosis confidence:
LIKELY

Impact:
₹2.2M
range = ₹1.7M–₹2.8M

Historical effectiveness:
FAVORABLE

Feasibility:
FEASIBLE

Monitoring:
revenue
orders
conversion

Success:
observed KPI trajectory moves toward
counterfactual trajectory


Stage 10
────────────────────────────
Persona-specific structured adaptation


Stage 11
────────────────────────────
LLM converts the structured decision
into natural-language communication
```

---

# 106. Final Architectural Position

Stage 9 is **not**:

```text
LLM recommendation generator
```

and it is **not**:

```text
cause → canned action lookup
```

It is:

```text
Stage 7 diagnosis
        +
Stage 8 quantified consequence
        +
declared business mechanisms
        +
company capabilities
        +
historical action outcomes
        ↓
structured action construction
        ↓
feasibility
        ↓
compatibility
        ↓
confidence-aware multi-objective selection
        ↓
primary + alternatives
        ↓
monitoring + success criteria
```

The defining rule is:

> **Stage 9 may decide what action follows from the established diagnosis, but it may never manufacture a diagnosis, manufacture an impact estimate, or manufacture certainty.**

The action is constructed deterministically from:

```text
CAUSE
→ MECHANISM
→ LEVER
→ ATOMIC ACTION
→ CONTEXT
```

The selection is based on:

```text
CONFIDENCE
+
IMPACT
+
FEASIBILITY
+
HISTORICAL EFFECTIVENESS
+
OPTIONAL EXECUTION METADATA
```

without pretending those dimensions have a universal mathematical exchange rate.

And the final output remains structured so that Stage 10 and Stage 11 can adapt and narrate it without changing the underlying decision.
