"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type { PipelineEvent, Stage7Summary, Stage3Summary, VerificationSummary } from "@/types/events";

interface Props {
  verificationEvent: PipelineEvent;
  stage7Event: PipelineEvent | undefined;
  stage3Event: PipelineEvent | undefined;
}

export default function VerdictView({ verificationEvent, stage7Event, stage3Event }: Props) {
  const vSummary = verificationEvent.summary as VerificationSummary;
  const s7Summary = stage7Event?.summary as Stage7Summary | undefined;
  const s3Summary = stage3Event?.summary as Stage3Summary | undefined;
  const containerRef = useRef<HTMLDivElement>(null);
  const verdictRef = useRef<HTMLDivElement>(null);

  const { matched_event_type, top1_hit, top3_hit, counterfactual_mae } = vSummary;
  const hasMatch = matched_event_type !== null;
  const wasCorrect = top1_hit === true;

  useEffect(() => {
    if (!containerRef.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(".verdict-header", { opacity: 0, y: -12 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" });
      gsap.fromTo(verdictRef.current, { scale: 0.92, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.6, delay: 0.3, ease: "back.out(1.4)" });
      gsap.fromTo(".verdict-row", { opacity: 0, x: -8 }, { opacity: 1, x: 0, duration: 0.4, stagger: 0.07, delay: 0.7, ease: "power2.out" });
    }, containerRef);
    return () => ctx.revert();
  }, [verificationEvent]);

  // Primary hypothesis from stage7
  const primaryHyp = s7Summary?.hypotheses?.find((h) => h.rank === 1);

  return (
    <div ref={containerRef} style={{ padding: "32px" }}>
      <div className="verdict-header" style={{ marginBottom: 24 }}>
        <p
          className="font-mono"
          style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}
        >
          Ground-Truth Verification
        </p>
        <h2 className="font-serif" style={{ fontSize: 22, color: "var(--ink)", margin: 0 }}>
          How did the pipeline do?
        </h2>
      </div>

      {/* Verdict badge */}
      <div
        ref={verdictRef}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 20px",
          borderRadius: 3,
          marginBottom: 28,
          background: hasMatch
            ? wasCorrect
              ? "#E6F0E6"
              : "var(--accent-soft)"
            : "var(--paper-deep)",
          border: `1px solid ${hasMatch ? (wasCorrect ? "#2E5C2E" : "var(--accent)") : "var(--border)"}`,
        }}
        id="verdict-badge"
      >
        <span style={{ fontSize: 18 }}>
          {!hasMatch ? "—" : wasCorrect ? "✓" : "✗"}
        </span>
        <span
          className="font-mono"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: !hasMatch ? "var(--ink-muted)" : wasCorrect ? "#2E5C2E" : "var(--accent)",
          }}
        >
          {!hasMatch
            ? "No matching event in window"
            : wasCorrect
            ? "Top-1 Correct"
            : top3_hit
            ? "Top-3 Correct"
            : "Not in Top-3"}
        </span>
      </div>

      {/* Detail rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Detected window */}
        {s3Summary && (
          <VerdictRow
            label="Detected Window"
            value={`Day ${s3Summary.window_start_day} — ${s3Summary.window_end_day}`}
            mono
          />
        )}

        {/* Matched event */}
        <VerdictRow
          label="Ground-Truth Event"
          value={matched_event_type ?? "None overlapping this window"}
          muted={!matched_event_type}
          mono
        />

        {/* Pipeline's top answer */}
        {primaryHyp && (
          <VerdictRow
            label="Pipeline Top-1 Hypothesis"
            value={primaryHyp.member_causes.join(" + ")}
            accent={wasCorrect}
            mono
          />
        )}

        {/* Top-1 / Top-3 */}
        <VerdictRow
          label="Top-1 Hit"
          value={top1_hit === null ? "n/a (no event)" : top1_hit ? "Yes" : "No"}
          accent={top1_hit === true}
          mono
        />
        <VerdictRow
          label="Top-3 Hit"
          value={top3_hit === null ? "n/a" : top3_hit ? "Yes" : "No"}
          accent={top3_hit === true}
          mono
        />

        {/* Counterfactual MAE */}
        <VerdictRow
          label="Counterfactual MAE"
          value={counterfactual_mae !== null && counterfactual_mae !== undefined ? counterfactual_mae.toFixed(4) : "None (not estimated)"}
          mono
        />

        {/* Batch scorecard — intentionally incomplete */}
        <div
          className="verdict-row"
          style={{
            marginTop: 8,
            padding: "10px 14px",
            background: "var(--paper-deep)",
            border: "1px solid var(--border)",
            borderRadius: 3,
          }}
        >
          <span
            className="font-mono"
            style={{ fontSize: 11, color: "var(--ink-faint)", letterSpacing: "0.07em" }}
          >
            Batch Scorecard
          </span>
          <span
            className="font-mono"
            style={{ fontSize: 13, color: "var(--ink-faint)", marginLeft: 12 }}
          >
            — (requires GET /verification/batch)
          </span>
        </div>
      </div>
    </div>
  );
}

function VerdictRow({
  label,
  value,
  mono,
  accent,
  muted,
}: {
  label: string;
  value: string;
  mono?: boolean;
  accent?: boolean;
  muted?: boolean;
}) {
  return (
    <div
      className="verdict-row"
      style={{ display: "flex", alignItems: "baseline", gap: 16, borderBottom: "1px solid var(--border)", paddingBottom: 10 }}
    >
      <span
        className="font-mono"
        style={{ fontSize: 11, color: "var(--ink-faint)", letterSpacing: "0.07em", textTransform: "uppercase", minWidth: 180, flexShrink: 0 }}
      >
        {label}
      </span>
      <span
        className={mono ? "font-mono" : ""}
        style={{
          fontSize: 13,
          color: accent ? "var(--accent)" : muted ? "var(--ink-faint)" : "var(--ink)",
          fontWeight: accent ? 600 : 400,
        }}
      >
        {value}
      </span>
    </div>
  );
}
