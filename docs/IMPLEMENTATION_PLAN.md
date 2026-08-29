# Implementation Plan

**Project:** Nidaa-AI — 6-day MVP sprint
**Read this after:** [Architecture](ARCHITECTURE.md)
**Pairs with:** [../PROGRESS.md](../PROGRESS.md) — every task ID below (`CORE-01`, `ING-03`, etc.) is a checklist row there. Update PROGRESS.md as you complete tasks, not this file. This file is the plan; PROGRESS.md is the state.

This expands the TRD's 6-day schedule (TRD §11) and the PRD's delivery plan (PRD §15) into task-level work, sized for **two people** covering four tracks (AI pipeline, Ingestion, Frontend, Data/Eval). Suggested split: **Person A = CORE + DATA**, **Person B = ING + FE**. Adjust freely, the task IDs don't change either way.

---

## Day 0 (before Day 1 officially starts) — accounts and access

Not in the original schedule but real: do this the night before so Day 1 isn't half gone by the time keys work.

- [ ] `SETUP-01` Create Groq account, generate `GROQ_API_KEY`, confirm current model IDs on the Groq console for `whisper-large-v3-turbo`, `whisper-large-v3`, `openai/gpt-oss-120b`, `qwen/qwen3.6-27b` (TRD's model note: this list moves)
- [ ] `SETUP-02` Acquire the burner SIM for the WhatsApp linked number (never a personal number — PRD §13.4)
- [ ] `SETUP-03` Both people install: Node 20+, Python 3.11+, `ffmpeg` on PATH
- [ ] `SETUP-04` Agree on the repo remote, branch strategy (recommend: short-lived feature branches into `main`, PR or direct push if just the two of you), and who merges the schema/contract freeze commit

---

## Day 1 — Contracts and scaffolding

**Exit criterion (PRD §15):** DB schema frozen, API contract frozen, Groq keys live, gazetteer CSV parsed and loaded, human baseline stopwatch run complete.

| ID | Task | Track | Depends on |
| :-- | :-- | :-- | :-- |
| `CORE-01` | Scaffold FastAPI app (`core/main.py`), health check route | CORE | SETUP-03 |
| `CORE-02` | Implement `db.py`: create tables from TRD §2 DDL exactly, WAL pragmas, a migration runner (even a simple "run DDL if not exists" is fine for 6 days) | CORE | CORE-01 |
| `CORE-03` | Implement `events.py`: append-event helper that runs inside the same transaction as any data write | CORE | CORE-02 |
| `CORE-04` | Stub the public routes (`/api/tickets`, `/api/metrics`, `/api/stream`, `/api/export/hxl.csv`) returning fixture JSON matching TRD §3.3 exactly, so FE and eval tooling can build against them today | CORE | CORE-01 |
| `CORE-05` | Groq smoke test: one script that calls both the STT and LLM endpoints with a hardcoded file/string and prints the raw response — confirms keys and model IDs actually work before building the pipeline around them | CORE | SETUP-01 |
| `ING-01` | Scaffold `ingest/index.js`, Baileys socket bootstrap, pairing-code login, persist `auth_state/` | ING | SETUP-02, SETUP-03 |
| `ING-02` | Confirm QR/pairing succeeds and inbound `messages.upsert` events log to console | ING | ING-01 |
| `ING-03` | Stub `POST /internal/ingest` calls against `CORE-04`'s stub routes (point at fixture core, not real pipeline yet) | ING | CORE-04 |
| `FE-01` | Static `dashboard/index.html` shell: header, left rail, map container, right rail — no data yet, matches the layout in UI-UX §5.1 | FE | — |
| `FE-02` | Mock ticket list rendered from a static JSON fixture (same shape as `CORE-04`'s stub) into the right rail and as map pins | FE | CORE-04 (contract, not the live route) |
| `DATA-01` | Download HDX COD-AB Pakistan admin 0-3 tables, flatten into `data/pak_gazetteer.csv` per the schema in TRD §4.5 | DATA | SETUP-03 |
| `DATA-02` | Hand-curate `data/aliases.json` for the top 40 flood-affected districts (start with the ones in TRD's example: Dadu, Sukkur, Khairpur, ...) | DATA | DATA-01 |
| `DATA-03` | Record the human baseline: stopwatch one person manually triaging a first-pass message set into a spreadsheet (PRD §2.1). This number anchors the whole demo — don't skip it because the gold set isn't finished yet; a rough baseline today beats no baseline on Day 6 | DATA | — |

**Day 1 sync point:** both people confirm TRD §2 (schema) and TRD §3 (API contract) are frozen. If either changed anything while scaffolding, reconcile it in the same conversation before moving to Day 2.

---

## Day 2 — Vertical slice

**Exit criterion:** one hardcoded audio file goes in, one structured row comes out and appears on the map. Ugly but end to end.

| ID | Task | Track | Depends on |
| :-- | :-- | :-- | :-- |
| `CORE-06` | Implement `pipeline/preflight.py`: ffprobe duration + RMS gate, per TRD §4.2 constants | CORE | CORE-01 |
| `CORE-07` | Implement `pipeline/stt.py`: Groq Whisper call, `verbose_json`, no confidence gate yet (add in Day 3) | CORE | CORE-05 |
| `CORE-08` | Implement `pipeline/extract.py`: system prompt wired from `prompts/system_extract.txt`, Pydantic schema validation, no fallback-model retry yet | CORE | CORE-05 |
| `CORE-09` | Wire stages 06-08 together synchronously in `main.py` (no queue/worker pool yet) for exactly one hardcoded test file, write result to `messages`/`tickets`, confirm an `events` row appears | CORE | CORE-06, CORE-07, CORE-08, CORE-03 |
| `CORE-10` | Real `GET /api/stream` SSE implementation (replaces the Day-1 stub), replaying from `events` table | CORE | CORE-09 |
| `ING-04` | `media.js`: download inbound audio, `ffmpeg -ar 16000 -ac 1 -c:a pcm_s16le` convert, write to `storage/audio/` | ING | ING-02 |
| `ING-05` | Wire real `POST /internal/ingest` call with real payload shape (sender hash, phone tail, audio path) against the now-real `core/` routes | ING | ING-04, CORE-09 |
| `FE-03` | Real SSE client (`app.js`): connect to `GET /api/stream`, render `ticket.created` events live instead of the static fixture | FE | CORE-10 |
| `FE-04` | Basic Leaflet map (`map.js`): OSM tiles, one pin per ticket, no styling polish yet | FE | FE-03 |
| `DATA-04` | Alias table extended toward full top-40 coverage | DATA | DATA-02 |

**Day 2 sync point:** run one real voice note through the full path (phone → `ingest/` → `core/` → SQLite → SSE → dashboard pin) together, even if it's rough. This is the first time the three runtimes actually meet — do it as a pair, not solo, so integration bugs get caught immediately instead of on Day 4.

---

## Day 3 — Real ingestion plus resilience

**Exit criterion:** Baileys live on the burner number, consent notice firing, queue and token bucket in place, confidence gate implemented.

| ID | Task | Track | Depends on |
| :-- | :-- | :-- | :-- |
| `CORE-11` | Implement `pipeline_queue.py`: `asyncio.Queue` + `WORKER_CONCURRENCY` workers + two token buckets (STT 15 RPM, LLM 25 RPM) per TRD §4.1 | CORE | CORE-09 |
| `CORE-12` | Retry/backoff: exponential + jitter, max 3 attempts, halve bucket refill for 60s on 429 | CORE | CORE-11 |
| `CORE-13` | STT confidence gate: `no_speech_prob`, `avg_logprob`, `compression_ratio`, min content tokens (TRD §4.3 constants) | CORE | CORE-07 |
| `CORE-14` | Escalation path: retry once on `STT_MODEL_ESCALATION`, then `status=audio_unintelligible`, skip extraction, fire reply template | CORE | CORE-13 |
| `CORE-15` | `queue_depth` published on a `metrics` SSE event every 2s | CORE | CORE-11 |
| `ING-06` | `consent.js`: `consent_ledger` state machine, first-contact notice fires once per sender, `BAND`/`STOP` sets revoked + purges | ING | ING-05 |
| `ING-07` | `outbound.js`: single reply queue, 1.5-3.0s jitter, global send cap | ING | ING-06 |
| `ING-08` | `templates.js`: consent notice, readback, unintelligible, location-missing — exact copy from PRD §3.1/3.2 and §6 | ING | ING-07 |
| `ING-09` | Wire `POST /internal/reply` handler: `core/` tells `ingest/` a template name + vars, `ingest/` composes and enqueues | ING | ING-08, CORE-14 |
| `FE-05` | Filter chips (urgency, district, time window), client-side filtering per UI-UX §6.1 (visual polish can wait, the toggle logic can't) | FE | FE-04 |
| `FE-06` | Urgency colour ramp on pins and rows per UI-UX §2.2 | FE | FE-05 |
| `DATA-05` | Generate the degraded-audio ladder script (`tools/degrade_audio.py`): rain/wind mixing at defined SNR steps | DATA | — |

**Day 3 sync point:** confirm the `audio_unintelligible` fork actually skips the LLM call — this is a safety-critical behaviour (PRD S4 metric), not just a nice-to-have. Test it together with one deliberately destroyed audio file.

---

## Day 4 — Intelligence and standards

**Exit criterion:** multi-intent extraction, idiom glossary, fuzzy geocoder with P-codes, urgency scoring, HXL export, correction loop live.

| ID | Task | Track | Depends on |
| :-- | :-- | :-- | :-- |
| `CORE-16` | Multi-intent extraction: confirm the prompt reliably returns multiple `records` entries for a multi-need message; add the fallback-model retry on validation failure (TRD §4.4) | CORE | CORE-08 |
| `CORE-17` | Load `prompts/glossary.json` into the system prompt at startup | CORE | CORE-16 |
| `CORE-18` | Implement `pipeline/geocode.py`: alias → exact → fuzzy (`rapidfuzz` WRatio ≥ 85) → none cascade (TRD §4.5) | CORE | DATA-01, DATA-04 |
| `CORE-19` | Implement `pipeline/urgency.py`: `max(model_urgency, rule_urgency)`, rule triggers from TRD §4.6 | CORE | CORE-16 |
| `CORE-20` | Implement `pipeline/dedupe.py`: `(adm2, intent, item, 15-min bucket)` key, sets `duplicate_of` | CORE | CORE-18 |
| `CORE-21` | `GET /api/export/hxl.csv`: real export, two-row header (human-readable + HXL hashtags) per TRD §7 | CORE | CORE-18, CORE-19 |
| `CORE-22` | Readback trigger: on medium/high confidence extraction, fire `POST /internal/reply` with `template=readback` | CORE | CORE-16, ING-09 |
| `CORE-23` | Handle sender replies `1`/`2` (routed from `ING-10`) → `verification_status = user_confirmed` / `user_disputed`, update ticket, emit event | CORE | CORE-22 |
| `ING-10` | Route `1`/`2` control keywords to the readback handler (never into the triage pipeline) per TRD §6 step 4 | ING | ING-09 |
| `FE-07` | Detail drawer: audio player, transcript, extracted fields, confidence bar, geocode method badge, verdict buttons | FE | FE-06 |
| `FE-08` | TTT header: median/p95 from `GET /api/metrics`, human baseline for contrast, live queue depth | FE | CORE-15, DATA-03 |
| `FE-09` | Pin/state shape semantics (solid/hollow/double-ring/badge/no-pin) per UI-UX §2.3 | FE | FE-07 |
| `DATA-06` | Validate the HXL export against the spec (open in a spreadsheet, confirm row 2 hashtags are exactly right) | DATA | CORE-21 |

**Day 4 sync point:** run the correction loop end to end together — send an ambiguous message, confirm the readback fires, reply `2`, confirm the ticket flips to disputed and jumps the queue (PRD §12.6). This is the single most differentiating feature in the product; don't let it be undemonstrated going into Day 5.

---

## Day 5 — Polish and proof

**Exit criterion:** dashboard filter chips (done Day 3, polish here), TTT header, burst test, acoustic test, SSE reconnect test, gold set accuracy run.

| ID | Task | Track | Depends on |
| :-- | :-- | :-- | :-- |
| `CORE-24` | Hardening pass: confirm every path in TRD §9's error taxonomy actually produces the documented `error_code` and behaviour | CORE | CORE-14, CORE-18 |
| `CORE-25` | `POST /api/simulate` behind `DEMO_MODE=true` (TRD §10) | CORE | CORE-09 |
| `ING-11` | Reconnect handling: `DisconnectReason.restartRequired` auto-reconnects, `loggedOut` hard-stops with a clear log | ING | ING-01 |
| `ING-12` | Confirm ban-safety pacing holds under the burst test (no bulk sends, no messaging a number that hasn't messaged first) | ING | ING-07 |
| `FE-10` | Offline OSM tile cache for the Sindh/south Punjab bounding box | FE | FE-04 |
| `FE-11` | Empty/error states per UI-UX §8 (no tickets yet, filters return nothing, WA session lost, rate limited, geocode/extraction failed) | FE | FE-07 |
| `FE-12` | SSE reconnect: confirm `Last-Event-ID` replay reaches identical state after a 30s disconnect | FE | FE-03 |
| `DATA-07` | Finish gold set: 25 messages (15 audio: 5 clean/5 moderate/5 severe, 10 text), each with a `label.json` — remember 8+ of the 15 audio samples must be **real human recordings**, not just TTS (TRD §8) | DATA | DATA-05 |
| `DATA-08` | Run `tools/burst_test.py`: 50 concurrent injections, assert zero 5xx / zero DB locks / zero unhandled 429s / exactly 50 rows | DATA | CORE-11, CORE-24 |
| `DATA-09` | Run the acoustic degradation ladder against the confidence gate, record the SNR point where it correctly gives up | DATA | DATA-05, CORE-13 |
| `DATA-10` | Compute accuracy (district + intent exact match) against the gold set, report with sample size attached | DATA | DATA-07 |

**Day 5 sync point:** both people run the full test suite (burst, acoustic, SSE reconnect, correction loop, consent) together at least once before end of day. Anything that fails here is a Day 6 fire, not a Day 6 feature.

---

## Day 6 — Freeze and rehearse

**No new features. Bug fixes only.** (TRD §11, PRD §15 — deliberate.)

| ID | Task | Track |
| :-- | :-- | :-- |
| `REL-01` | Feature freeze at noon. Anything not done ships as a stated limitation (PRD §13), not a rushed half-feature | Both |
| `REL-02` | Record the 90-second insurance video of the full live WhatsApp flow | ING + FE |
| `REL-03` | Run the entire demo once with the laptop in airplane mode, phone hotspot only | Both |
| `REL-04` | Verify `DEMO_MODE` simulator fallback works standalone, no WhatsApp connection at all | CORE |
| `REL-05` | Rehearse the full demo three times, at least once fully offline | Both |
| `REL-06` | Build the pitch deck around the measured TTT number, not a claimed one | DATA |
| `REL-07` | Final pass through the [Definition of Done checklist](TRD.md#12-definition-of-done) (TRD §12) — all 10 items, on a clean checkout | Both |

---

## Cross-cutting: Definition of Done

Before calling the MVP finished, verify all 10 items in [TRD §12](TRD.md#12-definition-of-done) on a clean checkout — a fresh `git clone`, fresh `.env`, fresh `npm install` / `pip install`. If it only works on one person's laptop, it isn't done.
