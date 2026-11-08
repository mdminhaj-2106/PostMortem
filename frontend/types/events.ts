// TypeScript types mirroring the real backend event shapes from orchestrator.py.
// Keep in sync with backend/orchestrator.py's yield sites — no guessed fields.

export interface TopSlice {
  kpi_name: string;
  dimension: string;
  slice_value: string;
  deviation_pct: number | null;
  eligibility: string;
}

export interface Hypothesis {
  hypothesis_id: string;
  member_causes: string[];
  confidence_bucket: string;  // "HIGH" | "MEDIUM" | "LOW"
  rank: number;
  evidence_count: number;
}

export interface TrajectoryPoint {
  day_offset: number;
  observed_value: number | null;
  baseline_value: number | null;
  counterfactual_value: number | null;
  estimated_impact: number | null;
}

export interface PersonaNarrative {
  narrative: string;
  usage: { input_tokens: number; output_tokens: number } | null;
}

// ─── Per-stage summary payloads ───────────────────────────────────────────

export interface Stage3Summary {
  priority_score: number | null;
  priority_basis: string;
  confidence: string;
  kpi_names: string[];
  window_start_day: number;
  window_end_day: number;
}

export interface Stage4Summary {
  slice_count: number;
  top_slices: TopSlice[];
}

export interface Stage5aSummary {
  top_cause: string | null;
  confidence: string;
  borrowed_count: number;
}

export interface Stage5bSummary {
  fork_reason: string;
  shares?: Record<string, number>;
}

export interface Stage6Summary {
  evidence_count: number;
}

export interface Stage7Summary {
  abstained: boolean;
  hypothesis_count: number;
  top_hypothesis_id: string | null;
  hypotheses: Hypothesis[];
}

export interface Stage8Summary {
  abstained_upstream: boolean;
  estimate_count: number;
  trajectories: Record<string, TrajectoryPoint[]>;  // keyed by hypothesis_id
}

export interface Stage9Summary {
  decision_status: string;
  action_type: string | null;
  primary_owner: string | null;
  primary_hypothesis_id: string | null;
  expected_impact: number | null;
  impact_lower: number | null;
  impact_upper: number | null;
}

export interface Stage10_11Summary {
  [persona: string]: PersonaNarrative;
}

export interface VerificationSummary {
  matched_event_type: string | null;
  top1_hit: boolean | null;
  top3_hit: boolean | null;
  counterfactual_mae: number | null;
}

// ─── Union event type ─────────────────────────────────────────────────────

export type StageName =
  | "stage3"
  | "stage4"
  | "stage5a_5c"
  | "stage5b"
  | "stage6"
  | "stage7"
  | "stage8"
  | "stage9"
  | "stage10_11"
  | "verification";

export type EventStatus = "completed" | "skipped" | "no_cluster";

export interface PipelineEvent {
  stage: StageName;
  status: EventStatus;
  summary: 
    | Stage3Summary
    | Stage4Summary
    | Stage5aSummary
    | Stage5bSummary
    | Stage6Summary
    | Stage7Summary
    | Stage8Summary
    | Stage9Summary
    | Stage10_11Summary
    | VerificationSummary
    | Record<string, unknown>;
}

// ─── Ordered stage metadata (for FlowRail rendering) ─────────────────────

export const PIPELINE_STAGES: Array<{
  stage: StageName;
  label: string;
  shortLabel: string;
}> = [
  { stage: "stage3",     label: "Cross-KPI Correlation",       shortLabel: "S3" },
  { stage: "stage4",     label: "Dimensional Decomposition",    shortLabel: "S4" },
  { stage: "stage5a_5c", label: "Fingerprint + Cold Start",     shortLabel: "S5" },
  { stage: "stage5b",    label: "Attribution Fork",             shortLabel: "S5b" },
  { stage: "stage6",     label: "Evidence Retrieval",           shortLabel: "S6" },
  { stage: "stage7",     label: "Hypothesis Debate",            shortLabel: "S7" },
  { stage: "stage8",     label: "Counterfactual Engine",        shortLabel: "S8" },
  { stage: "stage9",     label: "Recommendation Assembly",      shortLabel: "S9" },
  { stage: "stage10_11", label: "Persona + Narration",          shortLabel: "S10-11" },
  { stage: "verification", label: "Ground-Truth Verification",  shortLabel: "VFY" },
];
