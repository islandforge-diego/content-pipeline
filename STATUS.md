# Status & Handoff

Quick-start context for continuing this project on another machine (or a fresh
Claude Code session). The build context is in `CLAUDE.md`; this file is the
"where we are / what's next / how to run" snapshot.

## What this is
A local, config-driven content pipeline for Island Forge Studio. A Flask web UI
(`webui/`) takes a clip → transcribes (Whisper) → writes brand-voice captions with
platform-aware CTAs → uploads to S3 → schedules across 5 platforms via Buffer →
generates authentic IG stories → and publishes a client-facing preview site.

## Current state (working + on `main`)
- **Feed posts:** transcribe → captions (Sonnet draft, Haiku revise) → S3 (public
  `media/` prefix) → Buffer drafts across FB/IG/TikTok/LinkedIn/YouTube. Per-platform
  metadata handled (FB type=post, YouTube title+category+privacy+madeForKids).
- **Stories:** real photo/clip + light native text overlay (Georgia Bold, top third,
  no emojis) → IG story reminder (Buffer notification). Not flyer cards (Deba's ask).
- **Preview site:** two month-navigable calendars (Posts / Stories), pulled from
  Buffer (history since 2026-06-01, paginated). Published to GitHub Pages via the
  in-app "Publish to web" button or `content-preview/deploy.sh`.
  Live: https://islandforge-diego.github.io/deba-content-preview/clients/deba/
- **Tests:** `pytest tests/` (34 passing, offline).

## Run it (per machine setup)
1. **Python 3.13 venv** (system 3.14 has no PyTorch wheels):
   `/opt/homebrew/bin/python3.13 -m venv .venv`
2. `.venv/bin/python -m pip install -r pipeline/requirements.txt`
   (also `botocore[crt]` for SSO creds, `pillow`, `openai-whisper`)
3. `cp .env.example .env` → fill `ANTHROPIC_API_KEY`, `BUFFER_TOKEN` (and `CALENDLY_TOKEN` when doing KPIs)
4. `aws configure` (S3 bucket `debadouglas`, region us-east-2) — ffmpeg on PATH
5. `.venv/bin/python webui/app.py` → http://127.0.0.1:5050
   (port 5050, not 5000 — macOS AirPlay squats on 5000)

## Key facts
- Deba CTA keyword is **INVESTOR** (the brand deck's "BUS DRIVER" is retired).
- S3 `debadouglas` serves media via a **public `media/` prefix** (Buffer HEAD-checks
  URLs; presigned URLs reject HEAD). Rest of bucket stays private.
- Brand voice store: `config/clients/deba.brand.md` + `deba.examples.md` (edit these
  to steer captions; add approved posts to examples).
- AWS is currently on **root keys** — pending follow-up to switch to the scoped
  `studio-uploader` IAM user, then delete the root key.

## Performance / KPIs (built — pending Calendly token)
A **Performance tab** on the preview shows business KPIs:
- Reach / impressions / engagement (+ rate) summed from per-post Buffer metrics,
  top posts, per-platform breakdown, and a short AI "what's working" insight.
- **Bookings** show once `CALENDLY_TOKEN` is in `.env` (2FA-gated PAT from
  Calendly → Integrations → API & webhooks). Until then bookings render as "—".
- Code: `pipeline/calendly_api.py`, `pipeline/kpi_sync.py`, `buffer_api.posts_with_metrics`,
  Performance tab in `content-preview/generate.py`. Refreshes via the Preview/Publish buttons.
- Live data already rich (300+ historical sent posts with metrics).

## Next ideas (not yet built)
- ManyChat keyword-DM conversions; per-post booking attribution via UTM; trend charts.

(Original plan, for reference)
**Performance / KPIs tab** on the client preview — business-outcome focused:
- Lead with **Calendly bookings** + Buffer **reach/impressions**; simple summary +
  top posts; short AI "what's working" insight (seeds the caption feedback loop).
- Sources: **Buffer + Calendly** now (ManyChat later).
- New: `pipeline/calendly_api.py`, `pipeline/kpi_sync.py`; extend `buffer_api.py`
  (`aggregated_metrics`), `content-preview/generate.py` (Performance tab), wire into
  `/api/preview/publish`.
- **Prereq:** a Calendly Personal Access Token → `CALENDLY_TOKEN` in `.env`.
- Caveats: Buffer metrics only exist for *sent* posts; Calendly bookings are
  top-line (no per-post attribution without UTM).
