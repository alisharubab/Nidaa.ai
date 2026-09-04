# Nidaa-AI (ندا)

> A stranded person's WhatsApp voice note, recorded in the Urdu they actually speak, becomes a verified, HXL-tagged, map-pinned relief ticket in under five seconds — and the system tells the dispatcher out loud when it isn't sure.

Nidaa-AI is a 6-day MVP: an automated WhatsApp ingestion listener, multilingual speech transcription with an explicit confidence gate, structured LLM entity extraction mapped to UN OCHA HXL standards, deterministic offline P-code geocoding, and a real-time dispatcher command dashboard.

**Status:** **MVP Complete & Production-Hardened** — End-to-end multi-modal crisis pipeline (Preflight, Whisper STT, Groq LLM extraction, deterministic HDX P-code geocoder, Green API WhatsApp transport, real-time command console with CARTO basemaps, audio waveform players, and UN OCHA HXL export) live and operating at a measured **median TTT of 2.2 seconds (13.5× speedup)**. See [PROGRESS.md](PROGRESS.md) for live telemetry and task verification.

---

## The one number that matters

**Time-to-Triage (TTT):** wall-clock time from WhatsApp message receipt to a structured, map-visible ticket. Target: **median under 5.0 seconds**, measured against our own human-dispatcher baseline. See [docs/PRD.md §2](docs/PRD.md#2-north-star-metric-the-one-measurable-outcome).

---

## Repository structure

```
nidaa-ai/
├── ingest/       # Node 20+, Baileys — WhatsApp daemon, consent, outbound pacing
├── core/         # Python 3.11, FastAPI — pipeline, queue, SQLite, SSE
├── dashboard/    # Vanilla JS + Leaflet — zero-build dispatcher UI
├── data/         # Gazetteer, alias table, gold evaluation set
├── tools/        # Test audio generation, burst test, acoustic degradation, baseline timer
├── storage/audio/# Local media, 72h TTL (gitignored)
├── docs/         # PRD, TRD, UI/UX spec, architecture, implementation plan
└── PROGRESS.md   # Shared task tracker — what's done, what's left
```

Full module breakdown, ownership, and the frozen API/DB contract between runtimes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Documentation map

| Doc | What's in it |
| :-- | :-- |
| [docs/PRD.md](docs/PRD.md) | Product requirements: problem space, north star metric, consent/correction loop, personas, roadmap |
| [docs/TRD.md](docs/TRD.md) | Technical requirements: repo layout, DB schema, API contract, pipeline spec, system prompt, build schedule, definition of done |
| [docs/UI-UX-REQUIREMENTS.md](docs/UI-UX-REQUIREMENTS.md) | Design direction, colour/type tokens, components, motion system, accessibility floor |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module map, ownership split, contracts frozen on Day 1, how to build in parallel without blocking each other |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Day-by-day task breakdown with task IDs, matched 1:1 to PROGRESS.md |
| [PROGRESS.md](PROGRESS.md) | Live checklist — flip a box when a task actually works end to end |

**Start here if you're new to the project:** PRD → TRD → ARCHITECTURE → IMPLEMENTATION_PLAN.

---

## Getting started

### Prerequisites
* Node.js 20+
* Python 3.11+
* `ffmpeg` on your `PATH`
* A Groq API key ([console.groq.com](https://console.groq.com)) — confirm current model IDs before relying on this README; Groq's free-tier model lineup moves (see [docs/TRD.md](docs/TRD.md) model note)
* A dedicated WhatsApp number for the ingestion daemon (never your personal number)

### Setup

```bash
git clone <this-repo>
cd nidaa-ai
cp .env.example .env
# fill in GROQ_API_KEY and review the other values in .env
```

**Core (Python pipeline + API):**
```bash
cd core
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Ingest (Node WhatsApp daemon):**
```bash
cd ingest
npm install
node index.js
# scan the QR code / enter the pairing code on first run
```

To test the ingestion path without a paired phone, set `INGEST_TRANSPORT=telegram` in `.env` (Bot API long polling; needs a bot token from @BotFather) — consent, voice download, and the `/internal/ingest` contract all run unchanged. `whatsapp` (Baileys) is the primary transport for the demo.

**Dashboard:**
No build step. Open `dashboard/index.html` directly in a browser, or serve the folder with any static file server:
```bash
cd dashboard
python -m http.server 5500
```

### Demo mode (no WhatsApp needed)

Set `DEMO_MODE=true` in `.env` and use `POST /api/simulate` to inject a gold-set message through the real pipeline without a live phone. Useful for development and the required offline demo fallback (see [docs/TRD.md §10](docs/TRD.md#10-demo-resilience-plan)).

---

## Deploying to Render

`render.yaml` is a [Blueprint](https://render.com/docs/blueprint-spec) that provisions all four pieces in one go: a managed Postgres database, and web services for `core/`, `ingest/`, and `dashboard/`.

**Steps:**
1. Push this repo to GitHub (Render Blueprints deploy from a connected repo).
2. In the Render dashboard: **New +** → **Blueprint** → pick this repo. Render reads `render.yaml` and shows the four resources it's about to create.
3. You'll be prompted for the secrets marked `sync: false` in `render.yaml`: `GROQ_API_KEY`, `GREEN_API_ID_INSTANCE`, `GREEN_API_TOKEN`, `SENDER_HASH_SALT`. Same values as your local `.env`.
4. Apply. Render provisions `nidaa-db` (Postgres), then builds and deploys `nidaa-core`, `nidaa-ingest`, and `nidaa-dashboard`.

**What changes vs. local dev, and why:**
* `core/db.py` picks Postgres automatically once Render sets `DATABASE_URL` — same DAO functions, same schema shape, nothing to configure. Locally, with `DATABASE_URL` unset, it's still plain SQLite. See `docs/TRD.md` section 2's Postgres-support addendum.
* `ingest/` and `core/` run as separate Render services with separate disks, so a voice note's audio bytes are forwarded from ingest to core over `/internal/ingest` (base64) rather than passed as a shared file path — see `docs/TRD.md` section 3.1's audio-forwarding addendum. This is transparent; nothing to configure.
* `dashboard/config.js` is a checked-in empty placeholder; Render's static-site build command overwrites it with the real `nidaa-core` URL before publishing. Opening `dashboard/index.html` locally via `file://` is completely unaffected.

**Two things worth knowing before you rely on this for a live demo:**
* **`nidaa-ingest` is a background poller, not a request/response service** — it polls Green API for new WhatsApp messages roughly once a second. Render's free tier spins a web service down after 15 minutes with *no inbound HTTP traffic*, and that outbound polling doesn't count as inbound — so on the free plan, the WhatsApp bridge silently stops receiving messages 15 minutes after the last inbound hit. Two fixes, pick one: (a) upgrade `nidaa-ingest` to a paid instance type in the Render dashboard (removes spin-down entirely), or (b) point a free external uptime pinger (e.g. [UptimeRobot](https://uptimerobot.com), [cron-job.org](https://cron-job.org)) at `https://nidaa-ingest.onrender.com/health` every ~10 minutes to keep it awake. `core/` and `dashboard/` don't have this problem the same way — they only need to be awake when someone's actually using the dashboard.
* **`core/`'s free-tier `storage/audio/` is ephemeral** — it resets on restart/redeploy. This matches the app's own 72h audio-retention design (`docs/TRD.md` 3.1) rather than being a new gap, but if you want audio to survive a Render restart, add a persistent disk (commented-out block already in `render.yaml`) on a paid instance type.
* Per `docs/TRD.md` section 10's Demo Resilience Plan, `POST /api/simulate` (behind `DEMO_MODE=true`) works against the deployed `nidaa-core` exactly as it does locally, independent of whether `nidaa-ingest`/WhatsApp are reachable at all.

---

## Working as a team

Two people, three runtimes. The short version — full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):

* `ingest/`, `core/`, and `dashboard/` only ever talk to each other over the HTTP contract in [docs/TRD.md §3](docs/TRD.md#3-api-contract). No cross-imports.
* That contract, plus the DB schema in [docs/TRD.md §2](docs/TRD.md#2-database-schema-sqlite-wal), is **frozen after Day 1**. Change it only with the other person in the loop, in the same commit that updates the docs.
* Suggested split: one person on `core/` + `data/` (AI pipeline, geocoding, evaluation), the other on `ingest/` + `dashboard/` (WhatsApp integration, UI). Build against stubs/fixtures so neither side blocks on the other — see [docs/ARCHITECTURE.md §5](docs/ARCHITECTURE.md#5-working-in-parallel-without-blocking-each-other).
* Track daily progress in [PROGRESS.md](PROGRESS.md), not in your head or in chat.

---

## What this is not

Stated plainly, same as the PRD does: this cannot verify truth, dialect coverage is uneven (Saraiki/Balochi unsupported in the MVP), the WhatsApp integration is unofficial (Baileys, ToS risk), free-tier API limits are real, and geocoding resolves to a district centroid, not a rooftop. Full list: [docs/PRD.md §13](docs/PRD.md#13-limitations-and-risks-stated-plainly).

---

## License

Not yet decided. Add one before any public release.
