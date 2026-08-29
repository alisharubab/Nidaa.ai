# Nidaa-AI (ندا)

> A stranded person's WhatsApp voice note, recorded in the Urdu they actually speak, becomes a verified, HXL-tagged, map-pinned relief ticket in under five seconds — and the system tells the dispatcher out loud when it isn't sure.

Nidaa-AI is a 6-day MVP: an automated WhatsApp ingestion listener, multilingual speech transcription with an explicit confidence gate, structured LLM entity extraction mapped to UN OCHA HXL standards, deterministic offline P-code geocoding, and a real-time dispatcher command dashboard.

**Status:** early scaffold — repository structure, contracts, and specs are in place; pipeline/ingestion/dashboard implementation is in progress. See [PROGRESS.md](PROGRESS.md) for exactly what's done.

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
