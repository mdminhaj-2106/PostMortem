"use client";

import { useEffect, useReducer, useRef, useCallback } from "react";
import type { PipelineEvent, StageName } from "@/types/events";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const WS_BACKEND = BACKEND.replace(/^http/, "ws");

// ─── State ────────────────────────────────────────────────────────────────

export interface RunState {
  runId: string | null;
  events: PipelineEvent[];
  latestByStage: Partial<Record<StageName, PipelineEvent>>;
  activeStage: StageName | null;
  isFinished: boolean;
  isConnecting: boolean;
  error: string | null;
}

const initialState: RunState = {
  runId: null,
  events: [],
  latestByStage: {},
  activeStage: null,
  isFinished: false,
  isConnecting: false,
  error: null,
};

// ─── Reducer ──────────────────────────────────────────────────────────────

type Action =
  | { type: "START"; runId: string }
  | { type: "CONNECTED" }
  | { type: "EVENT"; event: PipelineEvent }
  | { type: "FINISHED" }
  | { type: "ERROR"; message: string }
  | { type: "RESET" };

const TERMINAL_STAGES: StageName[] = ["verification"];

function reducer(state: RunState, action: Action): RunState {
  switch (action.type) {
    case "START":
      return { ...initialState, runId: action.runId, isConnecting: true };
    case "CONNECTED":
      return { ...state, isConnecting: false };
    case "EVENT": {
      const event = action.event;
      const isTerminal =
        TERMINAL_STAGES.includes(event.stage) ||
        event.status === "no_cluster";
      return {
        ...state,
        events: [...state.events, event],
        latestByStage: { ...state.latestByStage, [event.stage]: event },
        activeStage: isTerminal ? null : event.stage,
        isFinished: isTerminal,
      };
    }
    case "FINISHED":
      return { ...state, isFinished: true, activeStage: null, isConnecting: false };
    case "ERROR":
      return { ...state, error: action.message, isConnecting: false };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────

export function useRunSocket(episodeId: number | null) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const runIdRef = useRef<string | null>(null);

  const startRun = useCallback(async (id: number) => {
    // Close any existing connection
    wsRef.current?.close();
    dispatch({ type: "RESET" });

    // POST /runs to get a run_id
    let runId: string;
    try {
      const res = await fetch(`${BACKEND}/runs?episode_id=${id}&use_llm=true`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`POST /runs failed: ${res.status}`);
      const data = await res.json();
      runId = data.run_id;
    } catch (err) {
      dispatch({ type: "ERROR", message: String(err) });
      return;
    }

    runIdRef.current = runId;
    dispatch({ type: "START", runId });

    // Connect WebSocket
    const ws = new WebSocket(`${WS_BACKEND}/ws/runs/${runId}`);
    wsRef.current = ws;

    ws.onopen = () => dispatch({ type: "CONNECTED" });

    ws.onmessage = (msg) => {
      try {
        const event: PipelineEvent = JSON.parse(msg.data as string);
        dispatch({ type: "EVENT", event });
        if (
          event.stage === "verification" ||
          event.status === "no_cluster"
        ) {
          ws.close();
        }
      } catch {
        // malformed frame — ignore
      }
    };

    ws.onerror = () =>
      dispatch({ type: "ERROR", message: "WebSocket connection error" });

    ws.onclose = () => {
      if (!state.isFinished) dispatch({ type: "FINISHED" });
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-start when episodeId prop changes
  useEffect(() => {
    if (episodeId !== null) startRun(episodeId);
    return () => {
      wsRef.current?.close();
    };
  }, [episodeId]); // eslint-disable-line react-hooks/exhaustive-deps

  return { ...state, startRun };
}
