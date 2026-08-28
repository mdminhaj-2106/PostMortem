# PS3 Round 1 — Pitch Content
## Concept Deck (3 slides) + Video (3 min)

**Strategy note before you build:** Round 1 explicitly rewards creativity and clear thinking over technical precision. Keep GBM/SHAP/causal-model language out of the deck and video entirely — that's Round 2 ammunition. Here, lead with the two ideas in plain English: *it knows when to shut up*, and *it tells apart causes that look identical on the surface*. Everything below is built around one running example so the deck and video reinforce each other.

---

## The End-to-End Walkthrough (your working example)

Use this exact scenario throughout — deck, video, and Q&A. It's the PRD's own example, so judges will recognize it and see you actually solved it.

**Input:** "Revenue is down 8% this month."

| Step | What the engine does | Plain-English output |
|---|---|---|
| 1. Detect | Checks the drop against expected range (trend, seasonality, day-of-week) instead of a flat threshold | "This isn't normal fluctuation — flagged as a significant anomaly." |
| 2. Decompose | Breaks the 8% down by region, segment, product, channel | "North region -15%, Enterprise -14%, Product A -21%. Not uniform — concentrated." |
| 3. Diagnose (fingerprint) | Reads the *shape* of the concentration — how many products, how localized, how the drop ramped in over time | "This shape (narrow, gradual, one region) doesn't look like a marketing cut or seasonality (those hit broad and fast). It looks like something account-specific." |
| 4. Gather evidence | Pulls CRM notes + support tickets tied to the affected accounts | "3 major Enterprise accounts logged reliability complaints in the 6 weeks *before* the dip." |
| 5. Weigh hypotheses | Ranks competing explanations instead of picking one | "Likely: product reliability (strong evidence). Possible: competitor activity in North (weaker evidence). Ruled out: seasonality, broad marketing pullback." |
| 6. Quantify | Estimates what revenue would look like without this factor | "Without the reliability-driven churn, revenue would be roughly flat." |
| 7. Recommend | Names the specific action, not generic advice | "Contact these 3 enterprise accounts before renewal and address their reliability complaints — not 'improve retention.'" |
| 8. Communicate | Exec sees 2 lines + confidence; analyst can drill into every step above | Same story, two depths. |

**The contrast that sells the pitch:** if that 8% had actually been a normal Monday-in-this-season fluctuation, Step 1 stops it right there — no invented story, no hypothesis theater. Most systems always find something to say. This one is willing to say nothing. That refusal, demonstrated, is worth more than any diagram.

---

## Slide 1 — The Problem

**Headline:** "Dashboards Tell You *What*. They Never Tell You *Why*."

- A KPI moves — a chart shows it. Explaining it still means an analyst manually digging through dashboards, queries, CRM notes, and tickets, often for days.
- Chatbot-on-dashboard tools don't fix this — they narrate the same chart in sentences, they don't investigate.
- Cost: slow decisions, generic advice ("improve retention"), causes missed because nobody had time to look.

**Visual suggestion:** A dashboard with a red -8% arrow, a thought-bubble "?" over it, a clock — then cut to a clean story card with the answer. Before/after in one image.

---

## Slide 2 — The Approach

**Headline:** "A Storytelling Engine — Not Another Chatbot Wrapper"

- The loop: **Detect → Decompose → Diagnose → Recommend → Communicate uncertainty**
- Two ideas that make this different:
  1. **It knows when to say nothing.** Most systems always generate a plausible-sounding cause. This one separates real signal from normal noise first — and reports "normal variation, no story" when that's the truth.
  2. **It reads the shape of the change, not just the size.** Two 8% drops can look identical on the surface but be caused by completely different things — a marketing cut hits broad and fast, a churn problem hits narrow and slow. The engine tells them apart by their signature across region, product, and timing — before it even opens a document.
- Fuses structured data (the numbers) with unstructured data (CRM notes, tickets, reviews) into one investigation, not two separate tools.

**Visual suggestion:** Simplified loop diagram (5 boxes, arrows, no jargon labels). Optionally, a small side-by-side: two identical-looking "-8%" line charts with different underlying shapes (one broad/instant, one narrow/ramping) to make the fingerprint idea visible in one glance.

---

## Slide 3 — Why It Matters

**Headline:** "From Data to Decision — In Minutes, Not Days"

- Walk the 8% example compressed to 3-4 lines: detect → concentrated in 3 enterprise accounts → reliability complaints preceded the dip → "contact these 3 accounts, here's the expected recovery."
- Every output carries a confidence label (Known / Likely / Possible / Unknown) — leaders get a straight answer, analysts get the full reasoning trail underneath.
- Business impact: days of manual digging → minutes; generic advice → named accounts and a quantified ask.

**Visual suggestion:** A mock "story card" screenshot-style graphic showing the final output — headline number, ranked causes with confidence %, one evidence snippet, one specific recommendation line.

---

## Video Script (3:00 max)

| Time | Visual | Voiceover |
|---|---|---|
| 0:00–0:15 | Dashboard, -8% in red, a person staring at it, clock ticking | "A KPI drops 8%. The dashboard shows you that. It doesn't tell you why — and finding out usually takes an analyst days." |
| 0:15–0:40 | Quick cuts / text overlays: "correlation ≠ explanation," "noise vs. signal," "generic advice" | "Most BI tools just add more charts. AI chatbots on top of dashboards just narrate the same numbers in sentences. Neither one investigates." |
| 0:40–1:00 | Simple animated loop: Detect → Decompose → Diagnose → Recommend → Communicate | "We built a KPI storytelling engine — it follows the same investigation an analyst would run, automatically." |
| 1:00–2:10 | Mock story-card walkthrough of the 8% example: decomposition breakdown → ranked hypotheses with confidence → CRM evidence snippet → recommendation line → recovery estimate | Narrate the 8-step walkthrough compressed: detects it's real, breaks it down by region and product, reads the shape of the drop, pulls supporting evidence, ranks the likely causes instead of guessing one, and lands on a specific, named recommendation. |
| 2:10–2:40 | Split-screen or second example: a KPI move that's genuinely just noise → system output: "Normal variation. No story generated." | "Here's the part almost nobody builds: knowing when *not* to explain. Most systems always find a cause. Ours is willing to say the data doesn't support one." |
| 2:40–3:00 | Team name, PS3 tag, one-line close | "From data, to insight, to decision — not just another dashboard." |

**Production tips:**
- You don't need a working live demo for Round 1 — a clean mockup (Figma frame, or even well-designed slides screen-recorded) of the story card is enough; the brief wants the *idea* communicated clearly, not a working prototype.
- Keep the noise-vs-signal example on screen long enough to actually read — it's your strongest 20 seconds, don't rush it.
- One voice, one throughline (the 8% example) — don't introduce a second scenario in the video; you already have one in the deck, reuse it so judges don't have to context-switch.
