"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type { PipelineEvent, Stage10_11Summary } from "@/types/events";

interface Props {
  event: PipelineEvent;
}

export default function PersonaForkView({ event }: Props) {
  const summary = event.summary as Stage10_11Summary;
  const containerRef = useRef<HTMLDivElement>(null);
  const lineRef = useRef<SVGPathElement>(null);

  const personas = Object.entries(summary);

  useEffect(() => {
    if (!containerRef.current) return;
    const ctx = gsap.context(() => {
      // Header
      gsap.fromTo(".persona-header", { opacity: 0, y: -12 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" });

      // Fork SVG draw
      if (lineRef.current) {
        const len = lineRef.current.getTotalLength();
        gsap.fromTo(
          lineRef.current,
          { strokeDasharray: len, strokeDashoffset: len },
          { strokeDashoffset: 0, duration: 0.6, delay: 0.3, ease: "power2.inOut" }
        );
      }

      // Cards slide in from opposite sides
      gsap.fromTo(
        ".persona-card-left",
        { opacity: 0, x: -24 },
        { opacity: 1, x: 0, duration: 0.5, delay: 0.7, ease: "power2.out" }
      );
      gsap.fromTo(
        ".persona-card-right",
        { opacity: 0, x: 24 },
        { opacity: 1, x: 0, duration: 0.5, delay: 0.7, ease: "power2.out" }
      );

      // Narrative text reveals line by line
      document.querySelectorAll(".narrative-line").forEach((line, i) => {
        gsap.fromTo(
          line,
          { opacity: 0, y: 4 },
          { opacity: 1, y: 0, duration: 0.3, delay: 1.0 + i * 0.04, ease: "power1.out" }
        );
      });
    }, containerRef);
    return () => ctx.revert();
  }, [event]);

  return (
    <div ref={containerRef} style={{ padding: "32px" }}>
      <div className="persona-header" style={{ marginBottom: 24 }}>
        <p
          className="font-mono"
          style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}
        >
          Stage 10 / 11 — Persona Narration
        </p>
        <h2 className="font-serif" style={{ fontSize: 22, color: "var(--ink)", margin: 0 }}>
          Two Lenses, One Story
        </h2>
      </div>

      {/* Fork SVG */}
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
        <svg width={120} height={32} aria-hidden="true" overflow="visible">
          <path
            ref={lineRef}
            d="M60,0 L60,16 L20,32 M60,16 L100,32"
            fill="none"
            stroke="var(--border)"
            strokeWidth={1.5}
          />
        </svg>
      </div>

      {/* Persona cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: personas.length > 1 ? "1fr 1fr" : "1fr",
          gap: 20,
        }}
      >
        {personas.map(([persona, data], i) => {
          const label = formatPersonaLabel(persona);
          const cardClass = i === 0 ? "persona-card-left" : "persona-card-right";
          const lines = data.narrative.split("\n").filter(Boolean);

          return (
            <div
              key={persona}
              className={cardClass}
              style={{
                background: "var(--paper-deep)",
                border: "1px solid var(--border)",
                borderRadius: 4,
                padding: "20px 22px",
              }}
              id={`persona-${persona}`}
            >
              <div style={{ marginBottom: 14 }}>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: "var(--ink-faint)",
                  }}
                >
                  {label}
                </span>
                {data.usage && (
                  <span
                    className="font-mono"
                    style={{
                      fontSize: 10,
                      color: "var(--ink-faint)",
                      marginLeft: 8,
                    }}
                  >
                    {data.usage.input_tokens + data.usage.output_tokens} tok
                  </span>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {lines.map((line, j) => (
                  <p
                    key={j}
                    className="font-serif narrative-line"
                    style={{
                      margin: 0,
                      fontSize: 14,
                      lineHeight: 1.75,
                      color: "var(--ink)",
                    }}
                  >
                    {line}
                  </p>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatPersonaLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
