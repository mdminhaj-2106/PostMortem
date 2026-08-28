# Deployment Reference

## Environments

| Environment | Status |
|---|---|
| Database (Neon) | **Live.** One shared Postgres project — see `.claude/reference/database.md`. No separate staging DB yet; the whole team works against the same instance. |
| App hosting (FastAPI / Next.js) | Not started — UNKNOWN, needs a decision once the backend exists |
| CI/CD | Not started — no `.github/workflows/` yet |

## Stack

- **DB host:** Neon (serverless Postgres). Free-tier storage was an active constraint during simulator generation (a full 400-episode run was scaled to 150 episodes specifically to stay safely inside free-tier limits — see project history / PR #3–7 discussion).
- **App hosting:** undecided.
- **CDN / frontend hosting:** undecided (likely Vercel once Next.js exists, given the stack, but not confirmed).

## Deploy process

Not applicable yet — nothing is deployed beyond the database itself.

## Environment variables

See `.env.example` at repo root — currently just `DATABASE_URL` (Neon connection string). Never commit `.env`.

## Secrets management

- `.env` is gitignored.
- `.env.example` documents shape only, no real values.
- The Neon connection string has been the only secret in play so far; revisit this whole doc once auth/API keys enter the picture with the FastAPI backend.
