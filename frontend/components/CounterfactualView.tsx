"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type { PipelineEvent, Stage8Summary, Stage9Summary, TrajectoryPoint } from "@/types/events";

interface Props {
  stage8Event: PipelineEvent;
  stage9Event: PipelineEvent | undefined;
}

// Build SVG path from trajectory points, breaking on null values
function buildPath(
  points: TrajectoryPoint[],
  getter: (p: TrajectoryPoint) => number | null,
  xScale: (day: number) => number,
  yScale: (v: number) => number
): string {
  if (!points.length) return "";
  const segments: string[] = [];
  let current = "";
  for (const p of points) {
    const val = getter(p);
    const x = xScale(p.day_offset);
    if (val === null) {
      if (current) segments.push(current);
      current = "";
    } else {
      const y = yScale(val);
      current += current ? ` L${x},${y}` : `M${x},${y}`;
    }
  }
  if (current) segments.push(current);
  return segments.join(" ");
}

export default function CounterfactualView({ stage8Event, stage9Event }: Props) {
  const summary8 = stage8Event.summary as Stage8Summary;
  const summary9 = stage9Event?.summary as Stage9Summary | undefined;
  const containerRef = useRef<HTMLDivElement>(null);
  const ghostPathRef = useRef<SVGPathElement>(null);

  // Pick trajectory for the primary hypothesis (stage9 tells us which)
  const primaryHypId = summary9?.primary_hypothesis_id;
  const trajectoryMap = summary8.trajectories;

  let trajectory: TrajectoryPoint[] | null = null;
  if (primaryHypId && trajectoryMap[primaryHypId]) {
    trajectory = trajectoryMap[primaryHypId];
  } else {
    // Fallback: first available trajectory
    const firstKey = Object.keys(trajectoryMap)[0];
    if (firstKey) trajectory = trajectoryMap[firstKey];
  }

  useEffect(() => {
    if (!containerRef.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(".cf-header", { opacity: 0, y: -12 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" });
      gsap.fromTo(".cf-chart", { opacity: 0 }, { opacity: 1, duration: 0.4, delay: 0.2, ease: "power1.out" });
      gsap.fromTo(".cf-meta", { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.4, stagger: 0.08, delay: 0.3, ease: "power2.out" });
    }, containerRef);

    // Draw the ghost (counterfactual) path via stroke-dashoffset
    if (ghostPathRef.current) {
      const length = ghostPathRef.current.getTotalLength();
      gsap.fromTo(
        ghostPathRef.current,
        { strokeDasharray: length, strokeDashoffset: length },
        { strokeDashoffset: 0, duration: 1.6, delay: 0.5, ease: "power2.inOut" }
      );
    }

    return () => ctx.revert();
  }, [stage8Event, stage9Event]);

  // No trajectory available
  if (!trajectory || trajectory.length === 0) {
    return (
      <div style={{ padding: "40px 32px" }}>
        <p className="font-mono" style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>Stage 8 — Counterfactual Engine</p>
        <h2 className="font-serif" style={{ fontSize: 22, color: "var(--ink)", margin: 0, marginBottom: 12 }}>No trajectory available</h2>
        <p style={{ color: "var(--ink-muted)", fontSize: 14 }}>
          {summary8.abstained_upstream
            ? "Stage 8 abstained (upstream abstention — no mechanism to estimate)."
            : "No estimated trajectory for the primary hypothesis."}
        </p>
      </div>
    );
  }

  // Chart dimensions
  const W = 560, H = 200, PAD = { top: 16, right: 16, bottom: 28, left: 48 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const days = trajectory.map((p) => p.day_offset);
  const allVals = trajectory.flatMap((p) => [p.observed_value, p.counterfactual_value, p.baseline_value]).filter((v): v is number => v !== null);
  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  const range = maxV - minV || 1;
  const minDay = Math.min(...days);
  const maxDay = Math.max(...days);
  const dayRange = maxDay - minDay || 1;

  const xScale = (d: number) => PAD.left + ((d - minDay) / dayRange) * innerW;
  const yScale = (v: number) => PAD.top + innerH - ((v - minV) / range) * innerH;

  const observedPath = buildPath(trajectory, (p) => p.observed_value, xScale, yScale);
  const cfPath = buildPath(trajectory, (p) => p.counterfactual_value, xScale, yScale);
  const baselinePath = buildPath(trajectory, (p) => p.baseline_value, xScale, yScale);

  // Y-axis ticks
  const tickCount = 4;
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => minV + (range * i) / tickCount);

  // Impact numbers from stage9
  const impact = summary9?.expected_impact;
  const lower = summary9?.impact_lower;
  const upper = summary9?.impact_upper;

  return (
    <div ref={containerRef} style={{ padding: "32px" }}>
      <div className="cf-header" style={{ marginBottom: 20 }}>
        <p className="font-mono" style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
          Stage 8 — Counterfactual Reveal
        </p>
        <h2 className="font-serif" style={{ fontSize: 22, color: "var(--ink)", margin: 0 }}>
          What would have happened without the event?
        </h2>
      </div>

      {/* Impact numbers */}
      {impact !== null && impact !== undefined && (
        <div className="cf-meta" style={{ display: "flex", gap: 24, marginBottom: 24 }}>
          <Metric label="Estimated Impact" value={fmt(impact)} accent />
          {lower !== null && lower !== undefined && (
            <Metric label="Lower Bound" value={fmt(lower)} />
          )}
          {upper !== null && upper !== undefined && (
            <Metric label="Upper Bound" value={fmt(upper)} />
          )}
        </div>
      )}

      {/* SVG chart */}
      <div className="cf-chart" style={{ overflowX: "auto" }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: "100%", maxWidth: W, height: "auto", display: "block" }}
          aria-label="Counterfactual trajectory chart"
        >
          {/* Y-axis ticks */}
          {ticks.map((t, i) => (
            <g key={i}>
              <line
                x1={PAD.left}
                y1={yScale(t)}
                x2={W - PAD.right}
                y2={yScale(t)}
                stroke="var(--border)"
                strokeWidth={0.5}
                strokeDasharray="3,3"
              />
              <text
                x={PAD.left - 6}
                y={yScale(t)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={9}
                fill="var(--ink-faint)"
                fontFamily="var(--font-mono)"
              >
                {fmtShort(t)}
              </text>
            </g>
          ))}

          {/* Baseline path */}
          <path
            d={baselinePath}
            fill="none"
            stroke="var(--border)"
            strokeWidth={1}
            strokeDasharray="4,4"
          />

          {/* Observed solid path */}
          <path
            d={observedPath}
            fill="none"
            stroke="var(--ink)"
            strokeWidth={1.5}
          />

          {/* Counterfactual ghost path (drawn by GSAP) */}
          <path
            ref={ghostPathRef}
            d={cfPath}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={1.5}
            strokeDasharray="6,3"
          />
        </svg>

        {/* Legend */}
        <div
          style={{
            display: "flex",
            gap: 20,
            marginTop: 10,
            flexWrap: "wrap",
          }}
        >
          <Legend color="var(--ink)" label="Observed" solid />
          <Legend color="var(--accent)" label="Counterfactual (no event)" dashed />
          <Legend color="var(--border)" label="Baseline" dashed />
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div>
      <p
        className="font-mono"
        style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.08em", textTransform: "uppercase", margin: 0 }}
      >
        {label}
      </p>
      <p
        className="font-mono"
        style={{ fontSize: 20, color: accent ? "var(--accent)" : "var(--ink)", fontWeight: 600, margin: "2px 0 0" }}
      >
        {value}
      </p>
    </div>
  );
}

function Legend({
  color,
  label,
  solid,
  dashed,
}: {
  color: string;
  label: string;
  solid?: boolean;
  dashed?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <svg width={24} height={8} aria-hidden="true">
        <line
          x1={0}
          y1={4}
          x2={24}
          y2={4}
          stroke={color}
          strokeWidth={1.5}
          strokeDasharray={dashed ? "4,3" : undefined}
        />
      </svg>
      <span
        className="font-mono"
        style={{ fontSize: 11, color: "var(--ink-faint)" }}
      >
        {label}
      </span>
    </div>
  );
}

function fmt(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(2);
}

function fmtShort(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}
