"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

interface Episode {
  episode_id: number;
}

interface Props {
  onSelect: (episodeId: number) => void;
}

export default function EpisodePicker({ onSelect }: Props) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${BACKEND}/episodes`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Episode[]>;
      })
      .then((data) => {
        setEpisodes(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(String(err));
        setLoading(false);
      });
  }, []);

  // Entrance animation
  useEffect(() => {
    if (!loading && episodes.length && gridRef.current && headerRef.current) {
      const ctx = gsap.context(() => {
        gsap.fromTo(
          headerRef.current,
          { opacity: 0, y: -16 },
          { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }
        );
        gsap.fromTo(
          gridRef.current!.children,
          { opacity: 0, y: 12 },
          {
            opacity: 1,
            y: 0,
            duration: 0.4,
            ease: "power2.out",
            stagger: 0.03,
            delay: 0.25,
          }
        );
      });
      return () => ctx.revert();
    }
  }, [loading, episodes.length]);

  const handleSelect = (id: number) => {
    setSelected(id);
    onSelect(id);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        padding: "80px 40px 60px",
        background: "var(--paper)",
      }}
    >
      {/* Header */}
      <div ref={headerRef} style={{ textAlign: "center", marginBottom: 56 }}>
        <p
          className="font-mono"
          style={{
            fontSize: 11,
            color: "var(--ink-faint)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: 12,
          }}
        >
          PostMortem — Causal Intelligence Pipeline
        </p>
        <h1
          className="font-serif"
          style={{ fontSize: 36, color: "var(--ink)", margin: 0, fontWeight: 600 }}
        >
          Select an Episode
        </h1>
        <p
          style={{
            marginTop: 12,
            color: "var(--ink-muted)",
            fontSize: 14,
            maxWidth: 480,
            lineHeight: 1.7,
          }}
        >
          Each episode is a 90-day synthetic business window with an injected
          causal event. The pipeline runs live — nine stages, real WebSocket
          stream, no pre-computed answers.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            color: "var(--accent)",
            fontFamily: "var(--font-mono)",
            fontSize: 13,
            marginBottom: 24,
            padding: "10px 16px",
            border: "1px solid var(--accent-soft)",
            borderRadius: 3,
            background: "var(--accent-soft)",
          }}
        >
          Could not reach backend: {error}. Is{" "}
          <code>uvicorn main:app --port 8000</code> running?
        </div>
      )}

      {/* Loading */}
      {loading && (
        <p className="font-mono" style={{ color: "var(--ink-faint)", fontSize: 13 }}>
          Loading episodes…
        </p>
      )}

      {/* Grid */}
      {!loading && episodes.length > 0 && (
        <div
          ref={gridRef}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(96px, 1fr))",
            gap: 8,
            width: "100%",
            maxWidth: 720,
          }}
        >
          {episodes.map((ep) => (
            <EpisodeCard
              key={ep.episode_id}
              id={ep.episode_id}
              isSelected={selected === ep.episode_id}
              onClick={() => handleSelect(ep.episode_id)}
            />
          ))}
        </div>
      )}

      {!loading && episodes.length === 0 && !error && (
        <p style={{ color: "var(--ink-muted)", fontSize: 14 }}>
          No episodes found in the database.
        </p>
      )}
    </div>
  );
}

function EpisodeCard({
  id,
  isSelected,
  onClick,
}: {
  id: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  const handleMouseEnter = () => {
    if (ref.current && !isSelected) {
      gsap.to(ref.current, {
        y: -2,
        backgroundColor: "var(--border)",
        duration: 0.15,
        ease: "power1.out",
      });
    }
  };

  const handleMouseLeave = () => {
    if (ref.current && !isSelected) {
      gsap.to(ref.current, {
        y: 0,
        backgroundColor: "var(--paper-deep)",
        duration: 0.2,
        ease: "power1.out",
      });
    }
  };

  return (
    <button
      ref={ref}
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        background: isSelected ? "var(--accent)" : "var(--paper-deep)",
        border: `1px solid ${isSelected ? "var(--accent)" : "var(--border)"}`,
        borderRadius: 3,
        padding: "12px 8px",
        cursor: "pointer",
        textAlign: "center",
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        fontWeight: isSelected ? 600 : 400,
        color: isSelected ? "#fff" : "var(--ink)",
        transition: "color 0.15s, border-color 0.15s",
        outline: "none",
      }}
      aria-pressed={isSelected}
      id={`episode-${id}`}
    >
      <span style={{ display: "block", fontSize: 10, color: isSelected ? "rgba(255,255,255,0.7)" : "var(--ink-faint)", marginBottom: 2 }}>ep</span>
      {id}
    </button>
  );
}
