"use client";

import { useParams, useRouter } from "next/navigation";
import { useRunSocket } from "@/lib/useRunSocket";
import FlowRail from "@/components/FlowRail";
import StageDetail from "@/components/StageDetail";

export default function RunPage() {
  const params = useParams<{ episodeId: string }>();
  const router = useRouter();
  const episodeId = params?.episodeId ? parseInt(params.episodeId, 10) : null;

  const {
    events,
    latestByStage,
    activeStage,
    isFinished,
    isConnecting,
    error,
  } = useRunSocket(episodeId);

  return (
    <div
      style={{
        height: "100dvh",
        display: "flex",
        flexDirection: "column",
        background: "var(--paper)",
        overflow: "hidden",
      }}
    >
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "12px 24px",
          borderBottom: "1px solid var(--border)",
          background: "var(--paper)",
          flexShrink: 0,
        }}
      >
        <button
          onClick={() => router.push("/")}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--ink-faint)",
            letterSpacing: "0.06em",
            padding: "4px 0",
          }}
          id="btn-back-home"
          aria-label="Back to episode picker"
        >
          ← Episodes
        </button>

        <div style={{ flex: 1 }} />

        <span
          className="font-mono"
          style={{ fontSize: 11, color: "var(--ink-faint)", letterSpacing: "0.06em" }}
        >
          Episode
        </span>
        <span
          className="font-mono"
          style={{ fontSize: 13, color: "var(--ink)", fontWeight: 600 }}
          id="run-episode-id"
        >
          {episodeId ?? "—"}
        </span>

        {isConnecting && (
          <span
            className="font-mono"
            style={{ fontSize: 11, color: "var(--accent)", letterSpacing: "0.06em" }}
          >
            Connecting…
          </span>
        )}
        {error && (
          <span
            className="font-mono"
            style={{ fontSize: 11, color: "var(--accent)", maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
            title={error}
          >
            Error: {error}
          </span>
        )}
      </div>

      {/* Flow Rail — Moment 2 persistent node strip */}
      <FlowRail
        events={events}
        latestByStage={latestByStage}
        activeStage={activeStage}
        isFinished={isFinished}
      />

      {/* Stage Detail — Moments 2-6 */}
      <StageDetail
        events={events}
        latestByStage={latestByStage}
        isFinished={isFinished}
      />
    </div>
  );
}
