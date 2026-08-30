"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type { PipelineEvent, StageName } from "@/types/events";
import { PIPELINE_STAGES } from "@/types/events";

interface Props {
  events: PipelineEvent[];
  latestByStage: Partial<Record<StageName, PipelineEvent>>;
  activeStage: StageName | null;
  isFinished: boolean;
}

export default function FlowRail({
  events,
  latestByStage,
  activeStage,
  isFinished,
}: Props) {
  const railRef = useRef<HTMLDivElement>(null);
  const pulseRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lineRefs = useRef<Record<string, SVGLineElement | null>>({});
  const prevActiveRef = useRef<StageName | null>(null);

  // Entrance animation on first mount
  useEffect(() => {
    if (!railRef.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        railRef.current!.children,
        { opacity: 0, y: 8 },
        { opacity: 1, y: 0, duration: 0.4, stagger: 0.04, ease: "power2.out" }
      );
    });
    return () => ctx.revert();
  }, []);

  // React to stage changes
  useEffect(() => {
    const prev = prevActiveRef.current;

    // Kill pulse on the previous active stage
    if (prev && pulseRefs.current[prev]) {
      gsap.killTweensOf(pulseRefs.current[prev]!);
      gsap.to(pulseRefs.current[prev]!, {
        scale: 1,
        opacity: 1,
        duration: 0.2,
      });
    }

    // Animate new active stage
    if (activeStage && pulseRefs.current[activeStage]) {
      gsap.fromTo(
        pulseRefs.current[activeStage]!,
        { scale: 1 },
        {
          scale: 1.5,
          duration: 0.8,
          ease: "power1.inOut",
          repeat: -1,
          yoyo: true,
        }
      );
    }

    // Draw the connector line for the just-completed stage
    if (prev && lineRefs.current[prev]) {
      const line = lineRefs.current[prev]!;
      gsap.fromTo(
        line,
        { strokeDashoffset: 100 },
        { strokeDashoffset: 0, duration: 0.5, ease: "power2.out" }
      );
    }

    prevActiveRef.current = activeStage;
  }, [activeStage]);

  const getStageStatus = (stage: StageName): "pending" | "active" | "completed" | "skipped" => {
    const event = latestByStage[stage];
    if (!event) {
      // It's active if it's the activeStage and not yet received
      return stage === activeStage ? "active" : "pending";
    }
    if (event.status === "skipped") return "skipped";
    if (stage === activeStage) return "active";
    return "completed";
  };

  const getAccentForStatus = (status: string) => {
    switch (status) {
      case "active":    return "var(--accent)";
      case "completed": return "var(--ink-muted)";
      case "skipped":   return "var(--border)";
      default:          return "var(--border)";
    }
  };

  return (
    <div
      ref={railRef}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        padding: "14px 24px",
        background: "var(--paper-deep)",
        borderBottom: "1px solid var(--border)",
        overflowX: "auto",
        flexShrink: 0,
      }}
      role="navigation"
      aria-label="Pipeline stage progress"
    >
      {PIPELINE_STAGES.map((stageInfo, i) => {
        const status = getStageStatus(stageInfo.stage);
        const color = getAccentForStatus(status);
        const isLast = i === PIPELINE_STAGES.length - 1;

        return (
          <div
            key={stageInfo.stage}
            style={{ display: "flex", alignItems: "center", flexShrink: 0 }}
          >
            {/* Node */}
            <div
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5 }}
              title={stageInfo.label}
            >
              <div
                ref={(el) => { pulseRefs.current[stageInfo.stage] = el; }}
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: color,
                  transition: "background 0.3s",
                  flexShrink: 0,
                }}
                id={`flow-node-${stageInfo.stage}`}
              />
              <span
                className="font-mono"
                style={{
                  fontSize: 9,
                  letterSpacing: "0.06em",
                  color: status === "active" ? "var(--accent)" : "var(--ink-faint)",
                  fontWeight: status === "active" ? 600 : 400,
                  transition: "color 0.3s",
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                }}
              >
                {stageInfo.shortLabel}
              </span>
            </div>

            {/* Connector line */}
            {!isLast && (
              <svg
                width={32}
                height={2}
                style={{ margin: "0 2px", flexShrink: 0, overflow: "visible" }}
                aria-hidden="true"
              >
                <line
                  x1={0}
                  y1={1}
                  x2={32}
                  y2={1}
                  stroke="var(--border)"
                  strokeWidth={1}
                />
                <line
                  ref={(el) => { lineRefs.current[stageInfo.stage] = el; }}
                  x1={0}
                  y1={1}
                  x2={32}
                  y2={1}
                  stroke={status === "completed" || status === "skipped" ? "var(--ink-muted)" : "transparent"}
                  strokeWidth={1.5}
                  strokeDasharray={32}
                  strokeDashoffset={status === "completed" || status === "skipped" ? 0 : 32}
                />
              </svg>
            )}
          </div>
        );
      })}

      {/* Live indicator */}
      <div
        style={{
          marginLeft: "auto",
          display: "flex",
          alignItems: "center",
          gap: 6,
          paddingLeft: 16,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: isFinished ? "var(--ink-muted)" : "var(--accent)",
            opacity: isFinished ? 0.5 : 1,
          }}
        />
        <span
          className="font-mono"
          style={{
            fontSize: 10,
            color: "var(--ink-faint)",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          {isFinished ? "complete" : events.length === 0 ? "waiting" : "live"}
        </span>
      </div>
    </div>
  );
}
