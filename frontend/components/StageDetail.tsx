"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type {
  PipelineEvent,
  StageName,
  Stage3Summary,
  Stage4Summary,
  Stage5aSummary,
  Stage5bSummary,
  Stage6Summary,
  Stage9Summary,
  Stage7Summary,
  Stage8Summary,
} from "@/types/events";
import DebateView from "./DebateView";
import CounterfactualView from "./CounterfactualView";
import PersonaForkView from "./PersonaForkView";
import VerdictView from "./VerdictView";

interface Props {
  events: PipelineEvent[];
  latestByStage: Partial<Record<StageName, PipelineEvent>>;
  isFinished: boolean;
}

// Which view to show — determined by the most advanced significant stage seen
function resolveView(
  latestByStage: Partial<Record<StageName, PipelineEvent>>
): "waiting" | "live-readout" | "debate" | "counterfactual" | "persona" | "verdict" {
  if (latestByStage["verification"]) return "verdict";
  if (latestByStage["stage10_11"]) return "persona";
  if (latestByStage["stage8"]) return "counterfactual";
  if (latestByStage["stage7"]) return "debate";
  // Any earlier stage: show live readout
  const earlyStages: StageName[] = ["stage3", "stage4", "stage5a_5c", "stage5b", "stage6", "stage9"];
  if (earlyStages.some((s) => latestByStage[s])) return "live-readout";
  return "waiting";
}

export default function StageDetail({ events, latestByStage, isFinished }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const prevViewRef = useRef<string | null>(null);

  const view = resolveView(latestByStage);

  // Cross-fade between views
  useEffect(() => {
    if (!containerRef.current || view === prevViewRef.current) return;
    if (prevViewRef.current !== null) {
      // Outgoing — quick fade
      gsap.fromTo(
        containerRef.current,
        { opacity: 0.3, y: 8 },
        { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }
      );
    }
    prevViewRef.current = view;
  }, [view]);

  // no_cluster early terminate
  const noCluster = events.some((e) => e.status === "no_cluster");

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        overflowY: "auto",
        background: "var(--paper)",
      }}
    >
      {noCluster && (
        <NoClusterState />
      )}

      {!noCluster && view === "waiting" && (
        <WaitingState />
      )}

      {!noCluster && view === "live-readout" && (
        <LiveReadout latestByStage={latestByStage} events={events} />
      )}

      {!noCluster && view === "debate" && latestByStage["stage7"] && (
        <DebateView event={latestByStage["stage7"]!} />
      )}

      {!noCluster && view === "counterfactual" && latestByStage["stage8"] && (
        <CounterfactualView
          stage8Event={latestByStage["stage8"]!}
          stage9Event={latestByStage["stage9"]}
        />
      )}

      {!noCluster && view === "persona" && latestByStage["stage10_11"] && (
        <PersonaForkView event={latestByStage["stage10_11"]!} />
      )}

      {!noCluster && view === "verdict" && latestByStage["verification"] && (
        <VerdictView
          verificationEvent={latestByStage["verification"]!}
          stage7Event={latestByStage["stage7"]}
          stage3Event={latestByStage["stage3"]}
        />
      )}
    </div>
  );
}

// ─── Sub-views ────────────────────────────────────────────────────────────

function WaitingState() {
  return (
    <div style={{ padding: "60px 32px", textAlign: "center" }}>
      <p
        className="font-mono"
        style={{ fontSize: 13, color: "var(--ink-faint)", letterSpacing: "0.08em" }}
      >
        Waiting for pipeline…
      </p>
    </div>
  );
}

function NoClusterState() {
  return (
    <div style={{ padding: "40px 32px" }}>
      <p
        className="font-mono"
        style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}
      >
        Stage 3 — No Cluster
      </p>
      <h2 className="font-serif" style={{ fontSize: 22, color: "var(--ink)", margin: 0, marginBottom: 12 }}>
        No significant anomaly cluster detected
      </h2>
      <p style={{ color: "var(--ink-muted)", fontSize: 14, maxWidth: 520, lineHeight: 1.7 }}>
        Stage 3 found no co-moving KPI windows that meet the significance threshold.
        This is a legitimate outcome — a noise episode — not an error. No story is
        manufactured.
      </p>
    </div>
  );
}

function LiveReadout({ latestByStage }: { latestByStage: Partial<Record<StageName, PipelineEvent>>; events: PipelineEvent[] }) {
  const s3 = latestByStage["stage3"]?.summary as Stage3Summary | undefined;
  const s4 = latestByStage["stage4"]?.summary as Stage4Summary | undefined;
  const s5 = latestByStage["stage5a_5c"]?.summary as Stage5aSummary | undefined;
  const s5b = latestByStage["stage5b"]?.summary as Stage5bSummary | undefined;
  const s6 = latestByStage["stage6"]?.summary as Stage6Summary | undefined;
  const s9 = latestByStage["stage9"]?.summary as Stage9Summary | undefined;

  return (
    <div style={{ padding: "32px" }}>
      <p
        className="font-mono"
        style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 20 }}
      >
        Live Stage Readout
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

        {/* Stage 3 */}
        {s3 && (
          <Section label="S3 — Cross-KPI Correlation">
            <Kv k="KPIs" v={s3.kpi_names.join(", ")} />
            <Kv k="Window" v={`Day ${s3.window_start_day} → ${s3.window_end_day}`} />
            <Kv k="Confidence" v={s3.confidence} />
            <Kv k="Priority Score" v={s3.priority_score?.toFixed(2) ?? "—"} />
          </Section>
        )}

        {/* Stage 4 */}
        {s4 && (
          <Section label="S4 — Dimensional Decomposition">
            <Kv k="Slices" v={String(s4.slice_count)} />
            {s4.top_slices.slice(0, 3).map((sl, i) => (
              <Kv
                key={i}
                k={`${sl.kpi_name} / ${sl.dimension}`}
                v={`${sl.slice_value}: ${sl.deviation_pct?.toFixed(1) ?? "—"}%`}
              />
            ))}
          </Section>
        )}

        {/* Stage 5a/5c */}
        {s5 && (
          <Section label="S5 — Fingerprint + Cold Start">
            <Kv k="Top Cause" v={s5.top_cause ?? "none"} />
            <Kv k="Confidence" v={s5.confidence} />
            {s5.borrowed_count > 0 && <Kv k="Borrowed Attributions" v={String(s5.borrowed_count)} />}
          </Section>
        )}

        {/* Stage 5b (if forked) */}
        {s5b && latestByStage["stage5b"]?.status === "completed" && (
          <Section label="S5b — Attribution Fork">
            <Kv k="Fork Reason" v={s5b.fork_reason} />
            {s5b.shares && Object.entries(s5b.shares).map(([cause, share]) => (
              <Kv key={cause} k={cause} v={`${(share * 100).toFixed(1)}%`} />
            ))}
          </Section>
        )}

        {/* Stage 6 */}
        {s6 && (
          <Section label="S6 — Evidence Retrieval">
            <Kv k="Evidence pieces" v={String(s6.evidence_count)} />
            {s6.evidence_count === 0 && (
              <p style={{ margin: 0, fontSize: 13, color: "var(--ink-faint)" }}>
                No supporting evidence found — Stage 7 will proceed on pattern alone.
              </p>
            )}
          </Section>
        )}

        {/* Stage 9 (may appear alongside debate/cf view briefly before transition) */}
        {s9 && (
          <Section label="S9 — Recommendation">
            <Kv k="Decision" v={s9.decision_status} />
            <Kv k="Action" v={s9.action_type ?? "—"} />
            <Kv k="Owner" v={s9.primary_owner ?? "—"} />
            {s9.expected_impact !== null && s9.expected_impact !== undefined && (
              <Kv k="Expected Impact" v={fmtImpact(s9.expected_impact)} accent />
            )}
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p
        className="font-mono"
        style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}
      >
        {label}
      </p>
      <div
        style={{
          background: "var(--paper-deep)",
          border: "1px solid var(--border)",
          borderRadius: 3,
          padding: "14px 18px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        {children}
      </div>
    </div>
  );
}

function Kv({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
      <span
        className="font-mono"
        style={{ fontSize: 11, color: "var(--ink-faint)", minWidth: 140, flexShrink: 0 }}
      >
        {k}
      </span>
      <span
        className="font-mono"
        style={{ fontSize: 13, color: accent ? "var(--accent)" : "var(--ink)", fontWeight: accent ? 600 : 400 }}
      >
        {v}
      </span>
    </div>
  );
}

function fmtImpact(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(2);
}
