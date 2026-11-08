---
name: agent-browser
description: Verify web UI behavior in a browser — responsive layout, forms, state transitions, and critical user flows. Not yet applicable — no frontend exists in this repo yet.
---

**Status: dormant.** No Next.js frontend has been started yet (see `PRD.md` roadmap). This skill activates once one exists.

## What to verify (once there's a UI)

Page loads without console errors · Executive Dashboard and Analyst View flows functional at all viewports · no text overflow · loading/empty/error/success states all correct for each pipeline stage's output · keyboard accessible.

Standard viewports: 375×812 (mobile), 768×1024 (tablet), 1440×900 (desktop).

Critical journeys (fill once the frontend exists, per `PRD.md`'s users table): Executive persona's fast-read flow, Analyst persona's drill-down/evidence-trace flow, the "normal variation, no story" decline state (must be visibly distinct from an actual finding, not just an empty dashboard).

## Evidence format

Browser + viewport checked, pages/flows verified, states verified, known gaps, screenshots for non-trivial changes.

## When to use

After any page/layout/component/CSS change, new routes, data-loading changes, before a demo/release.
