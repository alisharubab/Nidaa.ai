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
| Human baseline (median, ms) | 29940 ms (p95 33753 ms, n=6) — see caveat on DATA-03 | 2026-08-30 |
| System median TTT (ms) | _not yet measured_ | |
| System p95 TTT (ms) | _not yet measured_ | |
| Target | < 5000 ms median | |

---

## Day 0 — Accounts and access

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| SETUP-01 | Groq account + API key + model IDs confirmed | [x] | Ali, 2026-08-29 — key in .env, all 4 model IDs confirmed available on Groq console |
| SETUP-02 | Burner SIM acquired for WhatsApp | [x] | Ali — using personal SIM with WhatsApp on main phone |
| SETUP-03 | Node 20+, Python 3.11+, ffmpeg installed (both machines) | [x] | Ali — Node 20+, Python 3.12, ffmpeg 9.0.1 (via WinGet) |
| SETUP-04 | Branch strategy + merge owner agreed | [x] | Ali — direct push to master, small commits, TRD §2/§3 changes flagged via addendum |

## Day 1 — Contracts and scaffolding

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-01 | FastAPI app scaffold + health check | [x] | Alisha, 2026-08-29 — boots clean, `/health` returns real status |
| CORE-02 | `db.py`: tables from TRD §2 DDL, WAL pragmas, migration runner | [x] | Alisha — DDL + full DAO layer (messages/tickets/consent/metrics), tested via curl. Also: (1) `PRAGMA foreign_keys=ON` + real FK on `messages.sender_hash`; (2) split `verification_status`/`dispatcher_verdict`; (3) full CHECK-constraint pass on every enum/range/JSON-shaped column; (4) `geocode_score` normalized to always be 0-1 (fuzzy matches now store `WRatio/100.0`, not the raw 0-100 value) + range-checked, `audio_duration_s`/`ttt_ms` positivity-checked. 14 bad-data cases tested across both rounds, all correctly rejected with `IntegrityError`, full legit flow (incl. `/api/simulate`) still passes |
| CORE-03 | `events.py`: append-event helper, same-transaction writes | [x] | Alisha — verified via live SSE replay test |
| CORE-04 | Public routes stubbed with fixture JSON matching TRD §3.3 | [x] | Alisha — went further than the Day-1 stub: routes are real and DB-backed, not fixtures. Tickets stay empty until the pipeline (Day 2) or `/api/simulate` populates them |
| CORE-05 | Groq smoke test (STT + LLM, hardcoded input) | [x] | Alisha, 2026-08-30 — `core/smoke_test_groq.py`, run against a real edge-tts-generated Urdu voice note. **4/4 passing.** STT primary + escalation both transcribe real audio with confidence metrics in gate range; both LLMs produce perfectly-structured extractions. `LLM_MODEL_FALLBACK` (`qwen/qwen3.6-27b`) initially failed Groq's `json_object` mode outright (it's a reasoning model, emits `<think>` before answering) — root-caused via Groq's own Reasoning docs and fixed with two extra kwargs (`reasoning_format="hidden"`, `reasoning_effort="none"`), no model swap needed. Documented as a TRD §4.4 addendum + inline in `pipeline/extract.py` so `CORE-08`/`CORE-16` don't rediscover this the hard way |
| ING-01 | Baileys socket bootstrap, pairing-code login | [x] | Ali/Qoder, 2026-08-29 — full `startSock()` with `useMultiFileAuthState`, pairing-code login, reconnect on close, hard-stop on loggedOut, reply server on port 3000, jidMap for outbound routing. Tested: daemon boots, connects to WA socket, reply server listens. Pairing needs phone. Baileys logic now lives in `transports/whatsapp.js` (moved unchanged, one env-var flip away). |
| ING-02 | QR/pairing confirmed, inbound events logged | [ ] | Needs Ali's phone with burner SIM — set `PAIRING_PHONE_NUMBER` in .env |
| ING-03 | `POST /internal/ingest` stub calls against CORE-04 | [x] | Ali/Qoder — wired inside `handleMessage()`, posts full payload shape per TRD §3.1, also includes audio path/duration from downloadAndConvertToWav. Round-trips re-confirmed live via Telegram transport: text + audio rows in DB. |
| FE-01 | Static dashboard shell (header/rails/map container) | [x] | Ali/Qoder, 2026-08-29 — full shell: brand mark + marigold dot in header, TTT metrics area, live indicator with pulsing dot, left rail with queue nav + district totals + HXL export button, glass filter bar over map, map legend, waveform-glyph empty state, presentation mode flag. Typography classes per UI-UX §3. |
| FE-02 | Mock ticket list from static JSON fixture | [x] | Ali/Qoder — full ticket card per UI-UX §6.2: 3px urgency bar, urgency badge, district+P-code, 2-line-clamped items summary, waveform placeholder bars, state dot (confirmed/disputed/unconfirmed), Acknowledge button with verdict POST, aria-labels. Queue counts auto-update. Verified live: /api/simulate → SSE → card renders. **Fixed by Alisha, 2026-08-30:** `verificationState()` in `app.js` checked `verification_status === "dispatcher_verified"`, a value the CORE-02 schema split removed — Acknowledge was silently not updating the state dot/pin. Now checks `dispatcher_verdict === "verified"` instead. Confirmed live: click Acknowledge → dot flips to Confirmed, pin goes solid. |
| DATA-01 | HDX COD-AB Pakistan gazetteer CSV built | [x] | Alisha, 2026-08-30 — downloaded the real HDX resource (`pak_admin_boundaries.xlsx`, WFP SDI COD-AB), built `tools/build_gazetteer.py` to flatten it into `data/pak_gazetteer.csv` per the exact TRD §4.5 column spec. 577 tehsils, 160 districts, 7 provinces, zero missing lat/lon/pcode, validated with a script. Also fixed `/api/simulate`'s Dadu P-code, which had been a guessed placeholder (`PK602`) — real value is `PK703`, now corrected with the real tehsil centroid too |
| DATA-02 | `aliases.json` seeded for top 40 districts | [x] | Alisha, 2026-08-30 — 78 alias entries covering 43 real flood-prone districts (Sindh/Balochistan/South Punjab/KP), every target cross-checked to actually exist in `pak_gazetteer.csv` (zero broken aliases). Canonical spellings pulled straight from HDX, which often differ from common usage — e.g. `Kambar Shahdad Kot`, `D. I. Khan`, `Shaheed Benazir Abad` |
| DATA-03 | Human baseline stopwatch run recorded | [x] | Alisha, 2026-08-30 — real timed run completed: median 29940ms / p95 33753ms / n=6, live in `data/human_baseline.json` and already flowing through `/api/metrics` (`human_baseline_ms`), confirmed via curl, no restart needed. **Caveat, not a blocker:** this number is well under PRD §2.1's expected 90-300s range — likely because the dispatcher (Alisha) already knew these 6 messages' content going in, answers were quick/rough rather than validated, and there was no map cross-reference or spreadsheet entry (the real friction PRD §1.2 describes). Treat as a placeholder; a colder, more representative run (ideally alongside `DATA-07`'s 25-message gold set) should replace it before this number goes in the pitch deck |
| — | *(unscheduled)* Telegram dev/test transport in `ingest/transports/` (`INGEST_TRANSPORT` env var) | [x] | Ali/Qoder, 2026-08-29 — adapter pattern: transport-agnostic handler in index.js, Baileys in `transports/whatsapp.js` (unchanged), core/ + TRD contracts untouched (ARCHITECTURE §4 updated). Live-tested via @nidaa_ai_bot: text + 3.9s voice round-trips (16kHz mono WAV on disk + DB rows), consent notice exactly once, BAND→revoked+purged, post-BAND silent drop, photo ignored, /start filtered, /internal/reply synthetic delivery. |
| — | **Sync point:** schema (TRD §2) + API contract (TRD §3) frozen | [ ] | Several changes since the original freeze, all documented as addenda in `docs/TRD.md` §2/§3.1: consent endpoints (new), FK enforcement + `verification_status`/`dispatcher_verdict` split, full CHECK-constraint pass, `geocode_score` normalized to 0-1. Still needs both of you to actually read and confirm together — flip this box once he has |

## Day 2 — Vertical slice

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-06 | `pipeline/preflight.py` | [x] | Alisha, 2026-08-30 — real ffprobe/ffmpeg calls, tested against 3 real fixtures: normal speech (passes), 0.5s clip (`AUDIO_TOO_SHORT`), 2s silence (`AUDIO_SILENT`, -91dB measured) |
| CORE-07 | `pipeline/stt.py` (no gate yet) | [x] | Alisha — real Groq Whisper call, tested against real edge-tts audio, returns text/language/segments/model as a plain dict |
| CORE-08 | `pipeline/extract.py` (no fallback retry yet) | [x] | Alisha — real Groq call + Pydantic `ExtractionResponse` validation. Also built the fallback-retry path (pulled forward from `CORE-16`, see below) since it was trivial once `extract()` existed. **Anti-hallucination guard tested directly:** `ExtractionRecord` uses `extra="forbid"`, confirmed a payload containing `latitude`/`longitude` is rejected by Pydantic instead of silently ignored — a model trying to invent coordinates now fails validation and triggers the fallback/failed path, per hard rule 3 |
| CORE-09 | Stages wired synchronously, one hardcoded test file end to end | [x] | Alisha — real `/internal/ingest` now runs preflight→stt→extract inline (`_run_pipeline_sync` in `main.py`). Tested live: (1) multi-district text message → 2 separate tickets, both correctly Unlocated (no geocoder yet — intentional, see hard rule 3); (2) real audio message → full status trail `received→transcribed→extracted`, `ttt_ms` computed, transcript+STT confidence metrics now persisted to `raw_text`/`stt_*` columns (was a real gap, found and fixed while verifying); (3) silent audio → `preflight_failed`/`AUDIO_SILENT`, zero tickets, zero API calls made; (4) SSE event trail confirmed to capture the full lifecycle for both the success and failure paths. **Real finding along the way:** a garbled STT transcript (edge-tts mispronunciation) produced *confident-looking* gate metrics (avg_logprob -0.49) while being semantically nonsense — Whisper can be confidently wrong, which is exactly why `DATA-07` requires real human recordings, not just TTS, for any accuracy claim |
| CORE-10 | Real `GET /api/stream` SSE (replaces stub) | [x] | Alisha — tested with curl AND live in-browser, reconnect replay confirmed |
| ING-04 | `media.js`: download + ffmpeg convert to 16kHz mono wav | [x] | Ali/Qoder, 2026-08-29 — `convertToWav` was done by Person A; `downloadAndConvertToWav` now implemented in index.js: downloads via `downloadMediaMessage`, writes temp file, converts, cleans up, returns path + duration. Live-verified via Telegram: 3.9s ogg/opus → PCM 16kHz mono WAV. |
| ING-05 | Real `POST /internal/ingest` payload wired to real core routes | [x] | Ali/Qoder — fully wired in `handleMessage()`, same as ING-03. Real payload with sender_hash, phone_tail, audio_path, modality, duration, text, received_at. |
| FE-03 | Real SSE client rendering live `ticket.created` events | [x] | Alisha — verified live in browser: ticket card + map pin both rendered from a real SSE event, screenshot confirmed |
| FE-04 | Basic Leaflet map, one pin per ticket | [x] | Confirmed live — pin landed exactly on Dadu's coordinates |
| DATA-04 | Alias table extended toward full top-40 | [x] | Already satisfied by `DATA-02`'s work (2026-08-30) — 43 districts, exceeds the top-40 target, every target verified against the real gazetteer |
| — | **Sync point:** one real voice note, phone-to-pin, run together | [ ] | |

## Day 3 — Real ingestion plus resilience

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-11 | `queue.py`: asyncio queue + worker pool + token buckets | [ ] | |
| CORE-12 | Retry/backoff + 429 bucket-halving | [ ] | |
| CORE-13 | STT confidence gate (no_speech/logprob/compression/tokens) | [ ] | |
| CORE-14 | Escalation path → `audio_unintelligible`, skip extraction | [ ] | |
| CORE-15 | `queue_depth` on metrics SSE event, every 2s | [ ] | |
| ING-06 | `consent.js`: consent ledger state machine, BAND/STOP | [x] | Alisha — implemented against the new `/internal/consent/*` endpoints, tested standalone with `node -e` (no WhatsApp needed): first-contact notice, no-resend, BAND→revoked all confirmed. Live-confirmed end-to-end via Telegram 2026-08-29: notice exactly once, BAND→revoked + raw_text/audio_path purged in DB, post-revoke silent drop. |
| ING-07 | `outbound.js`: single reply queue, jittered pacing | [x] | Ali/Qoder, 2026-08-29 — live-confirmed: consent notice + reply-server message both delivered through the single jittered queue (1.5–3.0s); pump hardened so a failed send can no longer stall the queue. |
| ING-08 | `templates.js`: consent/readback/unintelligible/location copy | [~] | consent_notice + audio_unintelligible live-delivered via Telegram (the latter via synthetic `/internal/reply`); readback + location_missing copy awaits the pipeline (Day 4) — location copy still has an in-code TODO. |
| ING-09 | `POST /internal/reply` handler wired | [x] | Ali/Qoder, 2026-08-29 — reply server live on :3000; synthetic POST with a real sender_hash → template rendered + delivered to the Telegram chat. Core's pipeline will call it for real once readback lands (Day 4). |
| FE-05 | Filter chips (urgency/district/time), client-side filtering | [ ] | |
| FE-06 | Urgency colour ramp on pins/rows | [ ] | |
| DATA-05 | Degraded-audio ladder script (`degrade_audio.py`) | [ ] | |
| — | **Sync point:** confirm `audio_unintelligible` truly skips the LLM | [ ] | |

## Day 4 — Intelligence and standards

| ID | Task | Done | Owner / Notes |
| :-- | :-- | :--: | :-- |
| CORE-16 | Multi-intent extraction + fallback-model retry | [x] | Pulled forward, done as part of `CORE-08` — `extract_with_fallback()` already built and tested (both directly and via `CORE-09`'s live pipeline run). Multi-intent confirmed live: "Larkana aur Shikarpur" → 2 correctly separate tickets |
| CORE-17 | Glossary loaded into system prompt at startup | [ ] | |
| CORE-18 | `pipeline/geocode.py`: alias → exact → fuzzy → none | [ ] | |
| CORE-19 | `pipeline/urgency.py`: blended max score | [ ] | |
| CORE-20 | `pipeline/dedupe.py`: key-based near-duplicate flag | [ ] | |
| CORE-21 | Real `GET /api/export/hxl.csv` | [x] | Alisha — tested, two-row header confirmed correct (human-readable + HXL hashtags), one row per item |
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
| CORE-25 | `POST /api/simulate` behind `DEMO_MODE` | [x] | Alisha, 2026-08-30 — revisited now that `CORE-09` landed: no longer inserts a canned ticket, runs the real `_run_pipeline_sync` (same code path as `/internal/ingest`), optional `{"text": "..."}` body overrides the default message. Tested: default text → 1 ticket, custom multi-district text → 2 tickets, both correctly Unlocated (no geocoder yet, matches TRD §10 "nothing about the demo is faked") |
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
