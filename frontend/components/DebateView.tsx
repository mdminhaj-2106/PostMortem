"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type { PipelineEvent, StageName, Stage7Summary } from "@/types/events";

interface Props {
  event: PipelineEvent;  // the stage7 event
}

export default function DebateView({ event }: Props) {
  const summary = event.summary as Stage7Summary;
  const { hypotheses, abstained } = summary;
  const containerRef = useRef<HTMLDivElement>(null);
  const barRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Sort by rank ascending (rank 1 = best)
  const sorted = [...hypotheses].sort((a, b) => a.rank - b.rank);

  useEffect(() => {
    if (!containerRef.current) return;
    const ctx = gsap.context(() => {
      // Header slides in
      gsap.fromTo(
        ".debate-header",
        { opacity: 0, y: -12 },
        { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }
      );
      // Bars settle from left staggered
      barRefs.current.forEach((bar, i) => {
        if (!bar) return;
        gsap.fromTo(
          bar,
          { scaleX: 0, opacity: 0 },
          {
            scaleX: 1,
            opacity: 1,
            duration: 0.55,
            ease: "power3.out",
            delay: 0.2 + i * 0.1,
          }
        );
      });
      // Row meta text fades
      gsap.fromTo(
        ".debate-row-meta",
        { opacity: 0 },
        { opacity: 1, duration: 0.4, stagger: 0.08, delay: 0.5, ease: "power1.out" }
      );
    }, containerRef);
    return () => ctx.revert();
  }, [event]);

  const bucketColor = (bucket: string) => {
    switch (bucket?.toUpperCase()) {
      case "HIGH":   return { bg: "#E6F0E6", text: "#2E5C2E" };
      case "MEDIUM": return { bg: "#F5F0E0", text: "#6B5B00" };
      case "LOW":    return { bg: "var(--accent-soft)", text: "var(--accent)" };
      default:       return { bg: "var(--paper-deep)", text: "var(--ink-faint)" };
    }
  };

  if (abstained || sorted.length === 0) {
    return (
      <div style={{ padding: "40px 32px" }}>
        <div className="debate-header" style={{ marginBottom: 24 }}>
          <p className="font-mono" style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>Stage 7 — Hypothesis Debate</p>
          <h2 className="font-serif" style={{ fontSize: 22, color: "var(--ink)", margin: 0 }}>No hypotheses formed</h2>
        </div>
        <p style={{ color: "var(--ink-muted)", fontSize: 14 }}>
          Stage 7 abstained — insufficient evidence to propose a ranked hypothesis.
          This is an honest outcome, not an error.
        </p>
      </div>
    );
  }

  const maxEvidence = Math.max(...sorted.map((h) => h.evidence_count || 1), 1);

  return (
    <div ref={containerRef} style={{ padding: "32px" }}>
      <div className="debate-header" style={{ marginBottom: 28 }}>
        <p className="font-mono" style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
          Stage 7 — Hypothesis Debate
        </p>
        <h2 className="font-serif" style={{ fontSize: 22, color: "var(--ink)", margin: 0 }}>
          {sorted.length} {sorted.length === 1 ? "Hypothesis" : "Hypotheses"} Ranked
        </h2>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {sorted.map((h, i) => {
          const bc = bucketColor(h.confidence_bucket);
          const isWinner = i === 0;
          const barWidth = Math.max(8, Math.round((h.evidence_count / maxEvidence) * 100));

          return (
            <div
              key={h.hypothesis_id}
              id={`hypothesis-${h.hypothesis_id}`}
              style={{
                borderLeft: `2px solid ${isWinner ? "var(--accent)" : "var(--border)"}`,
                paddingLeft: 16,
              }}
            >
              <div className="debate-row-meta" style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                {/* Rank */}
                <span className="font-mono" style={{ fontSize: 11, color: isWinner ? "var(--accent)" : "var(--ink-faint)", fontWeight: 600, minWidth: 24 }}>
                  #{h.rank}
                </span>
                {/* Causes */}
                <span style={{ fontSize: 13, color: isWinner ? "var(--ink)" : "var(--ink-muted)", fontWeight: isWinner ? 500 : 400, flex: 1 }}>
                  {h.member_causes.join(" + ")}
                </span>
                {/* Confidence bucket */}
                <span
                  className="bucket"
                  style={{ background: bc.bg, color: bc.text }}
                >
                  {h.confidence_bucket}
                </span>
                {/* Evidence count */}
                <span className="font-mono" style={{ fontSize: 11, color: "var(--ink-faint)", whiteSpace: "nowrap" }}>
                  {h.evidence_count} ev
                </span>
              </div>

              {/* Animated evidence bar */}
              <div
                style={{
                  height: 3,
                  background: "var(--paper-deep)",
                  borderRadius: 2,
                  overflow: "hidden",
                }}
              >
                <div
                  ref={(el) => { barRefs.current[i] = el; }}
                  style={{
                    height: "100%",
                    width: `${barWidth}%`,
                    background: isWinner ? "var(--accent)" : "var(--ink-faint)",
                    borderRadius: 2,
                    transformOrigin: "left center",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
