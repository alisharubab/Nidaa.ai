# Progress Tracker

**Project:** Nidaa-AI
**How to use this file:** this is the single shared source of truth for "what's done and what's left." Task IDs match [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — look a task up there for full context, then flip its checkbox here when it's done.

**Rules for keeping this useful:**
1. Check a box only when the task actually works end to end, not when the code is written. "Written but untested" stays unchecked.
2. Put your name/initial and the date in the Owner/Notes column when you pick up or finish a task — don't leave it blank, that's how two people end up building the same thing.
3. If you change scope on a task (skip it, descope it, discover it needs splitting), say so in Notes rather than silently leaving it unchecked forever.
4. Update this file in the same sitting you finish the work — not at end of day, not "later."

---

## North Star Metric

| Metric | Value | Last updated |
| :-- | :-- | :-- |
| Human baseline (median, ms) | _not yet measured_ | |
| System median TTT (ms) | _not yet measured_ | |
| System p95 TTT (ms) | _not yet measured_ | |
| Target | < 5000 ms median | |

---

## Day 0 — Accounts and access

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| SETUP-01 | Groq account + API key + model IDs confirmed | [ ] | |
| SETUP-02 | Burner SIM acquired for WhatsApp | [ ] | |
| SETUP-03 | Node 20+, Python 3.11+, ffmpeg installed (both machines) | [ ] | |
| SETUP-04 | Branch strategy + merge owner agreed | [ ] | |

## Day 1 — Contracts and scaffolding

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-01 | FastAPI app scaffold + health check | [x] | Claude, 2026-08-29 — boots clean, `/health` returns real status |
| CORE-02 | `db.py`: tables from TRD §2 DDL, WAL pragmas, migration runner | [x] | Claude — DDL + full DAO layer (messages/tickets/consent/metrics), tested via curl |
| CORE-03 | `events.py`: append-event helper, same-transaction writes | [x] | Claude — verified via live SSE replay test |
| CORE-04 | Public routes stubbed with fixture JSON matching TRD §3.3 | [x] | Claude — went further than the Day-1 stub: routes are real and DB-backed, not fixtures. Tickets stay empty until the pipeline (Day 2) or `/api/simulate` populates them |
| CORE-05 | Groq smoke test (STT + LLM, hardcoded input) | [ ] | Script not written yet — needs your `GROQ_API_KEY` first |
| ING-01 | Baileys socket bootstrap, pairing-code login | [ ] | Code not started — needs your burner-SIM pairing to test |
| ING-02 | QR/pairing confirmed, inbound events logged | [ ] | Depends on ING-01 + your phone |
| ING-03 | `POST /internal/ingest` stub calls against CORE-04 | [ ] | Can be tested with `curl` right now, no WhatsApp needed |
| FE-01 | Static dashboard shell (header/rails/map container) | [x] | Already scaffolded, confirmed rendering |
| FE-02 | Mock ticket list from static JSON fixture | [~] | Superseded — went straight to the real SSE client (FE-03) instead of a static fixture |
| DATA-01 | HDX COD-AB Pakistan gazetteer CSV built | [ ] | Needs a file download from HDX — ask before I do this (see summary) |
| DATA-02 | `aliases.json` seeded for top 40 districts | [~] | 5 example districts seeded from the TRD; needs expansion to 40 |
| DATA-03 | Human baseline stopwatch run recorded | [ ] | Needs a human with a stopwatch — see summary |
| — | **Sync point:** schema (TRD §2) + API contract (TRD §3) frozen | [ ] | One contract change made + documented (consent endpoints, TRD §3.1 addendum) — both of you should read and confirm it together |

## Day 2 — Vertical slice

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-06 | `pipeline/preflight.py` | [ ] | |
| CORE-07 | `pipeline/stt.py` (no gate yet) | [ ] | |
| CORE-08 | `pipeline/extract.py` (no fallback retry yet) | [ ] | |
| CORE-09 | Stages wired synchronously, one hardcoded file end to end | [ ] | |
| CORE-10 | Real `GET /api/stream` SSE (replaces stub) | [x] | Claude — tested with curl AND live in-browser, reconnect replay confirmed |
| ING-04 | `media.js`: download + ffmpeg convert to 16kHz mono wav | [~] | `convertToWav` implemented; `downloadAndConvert` (the Baileys-specific half) still TODO |
| ING-05 | Real `POST /internal/ingest` payload wired to real core routes | [ ] | Core side is ready and tested; Node side not wired yet |
| FE-03 | Real SSE client rendering live `ticket.created` events | [x] | Claude — verified live in browser: ticket card + map pin both rendered from a real SSE event, screenshot confirmed |
| FE-04 | Basic Leaflet map, one pin per ticket | [x] | Confirmed live — pin landed exactly on Dadu's coordinates |
| DATA-04 | Alias table extended toward full top-40 | [ ] | |
| — | **Sync point:** one real voice note, phone-to-pin, run together | [ ] | |

## Day 3 — Real ingestion plus resilience

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-11 | `queue.py`: asyncio queue + worker pool + token buckets | [ ] | |
| CORE-12 | Retry/backoff + 429 bucket-halving | [ ] | |
| CORE-13 | STT confidence gate (no_speech/logprob/compression/tokens) | [ ] | |
| CORE-14 | Escalation path → `audio_unintelligible`, skip extraction | [ ] | |
| CORE-15 | `queue_depth` on metrics SSE event, every 2s | [ ] | |
| ING-06 | `consent.js`: consent ledger state machine, BAND/STOP | [x] | Claude — implemented against the new `/internal/consent/*` endpoints, tested standalone with `node -e` (no WhatsApp needed): first-contact notice, no-resend, BAND→revoked all confirmed |
| ING-07 | `outbound.js`: single reply queue, jittered pacing | [ ] | |
| ING-08 | `templates.js`: consent/readback/unintelligible/location copy | [ ] | |
| ING-09 | `POST /internal/reply` handler wired | [ ] | |
| FE-05 | Filter chips (urgency/district/time), client-side filtering | [ ] | |
| FE-06 | Urgency colour ramp on pins/rows | [ ] | |
| DATA-05 | Degraded-audio ladder script (`degrade_audio.py`) | [ ] | |
| — | **Sync point:** confirm `audio_unintelligible` truly skips the LLM | [ ] | |

## Day 4 — Intelligence and standards

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-16 | Multi-intent extraction + fallback-model retry | [ ] | |
| CORE-17 | Glossary loaded into system prompt at startup | [ ] | |
| CORE-18 | `pipeline/geocode.py`: alias → exact → fuzzy → none | [ ] | |
| CORE-19 | `pipeline/urgency.py`: blended max score | [ ] | |
| CORE-20 | `pipeline/dedupe.py`: key-based near-duplicate flag | [ ] | |
| CORE-21 | Real `GET /api/export/hxl.csv` | [x] | Claude — tested, two-row header confirmed correct (human-readable + HXL hashtags), one row per item |
| CORE-22 | Readback trigger on medium/high confidence | [ ] | |
| CORE-23 | Handle `1`/`2` replies → confirmed/disputed | [ ] | |
| ING-10 | Route `1`/`2` control keywords to readback handler | [ ] | |
| FE-07 | Detail drawer (audio, transcript, fields, confidence, verdicts) | [ ] | |
| FE-08 | TTT header (median/p95/baseline/queue depth) | [ ] | |
| FE-09 | Pin/state shape semantics | [ ] | |
| DATA-06 | HXL export validated against spec | [ ] | |
| — | **Sync point:** correction loop end to end, together | [ ] | |

## Day 5 — Polish and proof

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-24 | Hardening pass across full error taxonomy (TRD §9) | [ ] | |
| CORE-25 | `POST /api/simulate` behind `DEMO_MODE` | [~] | Claude — tested, `DEMO_MODE` gate works (403 when off). Currently inserts a canned ticket rather than replaying through the real pipeline, since the pipeline isn't wired yet — revisit once CORE-06..09 land |
| ING-11 | Reconnect handling (restartRequired / loggedOut) | [ ] | |
| ING-12 | Ban-safety pacing confirmed under burst test | [ ] | |
| FE-10 | Offline OSM tile cache for demo bounding box | [ ] | |
| FE-11 | Empty/error states (UI-UX §8) | [ ] | |
| FE-12 | SSE reconnect / `Last-Event-ID` replay verified | [ ] | |
| DATA-07 | Gold set finished (25 msgs, 8+ real audio recordings) | [ ] | |
| DATA-08 | Burst test: 50 concurrent, zero crashes/locks/429s | [ ] | |
| DATA-09 | Acoustic degradation ladder run, SNR give-up point recorded | [ ] | |
| DATA-10 | Gold-set accuracy computed, sample size reported | [ ] | |
| — | **Sync point:** full test suite run together at least once | [ ] | |

## Day 6 — Freeze and rehearse

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| REL-01 | Feature freeze at noon | [ ] | |
| REL-02 | 90-second insurance video recorded | [ ] | |
| REL-03 | Full demo run in airplane mode + hotspot | [ ] | |
| REL-04 | `DEMO_MODE` simulator fallback verified standalone | [ ] | |
| REL-05 | Demo rehearsed 3x, at least once fully offline | [ ] | |
| REL-06 | Pitch deck built around the measured TTT number | [ ] | |
| REL-07 | Definition of Done checklist passed on a clean checkout | [ ] | |

---

## Definition of Done (TRD §12) — final gate

Check these only on a **fresh clone**, not your dev machine's warm state.

- [ ] 1. Real-phone voice note → mapped, HXL-tagged ticket, median TTT < 5s
- [ ] 2. Consent notice fires exactly once per sender; `BAND` stops + purges
- [ ] 3. Noise-destroyed voice note → orange `AUDIO_UNINTELLIGIBLE`, LLM never called
- [ ] 4. No-location message → null-coordinate ticket in Unlocated queue, no invented coordinates anywhere
- [ ] 5. Three-district message → three separate tickets, three P-codes
- [ ] 6. Readback fires; replying `2` → disputed + top of review queue
- [ ] 7. 50-message burst: zero crashes, zero DB locks, zero unhandled rate-limit errors
- [ ] 8. 30s browser disconnect → identical state on reconnect
- [ ] 9. HXL CSV export opens cleanly with a valid hashtag row
- [ ] 10. Full demo runs from the simulator with WhatsApp fully disconnected
