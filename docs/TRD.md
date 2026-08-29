# Technical Requirements Document (TRD)

**Project:** Nidaa-AI (Automated Multi-Modal Crisis Triage Engine)
**Version:** 1.0.0 (companion to PRD v4.0.0)
**Scope:** Everything an engineer needs to build the 6-day MVP without asking a question.

---

## 1. Runtime and Repository Layout

```
nidaa-ai/
├── ingest/                       # Node 20+, Baileys daemon
│   ├── index.js                  # socket bootstrap, QR pairing, event handlers
│   ├── consent.js                # first-contact notice, BAND/STOP handling
│   ├── outbound.js               # human-paced reply queue (1.5-3.0s jitter)
│   ├── media.js                  # download + convert to 16kHz mono wav
│   └── auth_state/               # Baileys credentials (gitignored)
│
├── core/                         # Python 3.11, FastAPI
│   ├── main.py                   # app, routes, SSE
│   ├── pipeline/
│   │   ├── preflight.py          # ffprobe duration + RMS gate
│   │   ├── stt.py                # Groq Whisper + confidence gate + escalation
│   │   ├── extract.py            # LLM structured extraction
│   │   ├── geocode.py            # offline gazetteer + rapidfuzz
│   │   ├── urgency.py            # rule + model blended score
│   │   └── dedupe.py             # near-duplicate flagging
│   ├── pipeline_queue.py         # asyncio queue, worker pool, token bucket
│   ├── db.py                     # SQLite WAL, migrations, DAO
│   ├── events.py                 # monotonic event log for SSE replay
│   ├── prompts/
│   │   ├── system_extract.txt
│   │   └── glossary.json
│   └── config.py
│
├── data/
│   ├── pak_gazetteer.csv         # built from HDX COD-AB admin 0-3
│   ├── aliases.json              # hand-curated Roman Urdu spelling variants
│   └── gold_set/                 # 25 labelled evaluation messages + audio
│
├── dashboard/
│   ├── index.html                # zero-build SPA
│   ├── app.js                    # SSE client, filters, table
│   ├── map.js                    # Leaflet layers, pin semantics
│   └── styles.css
│
├── tools/
│   ├── make_test_audio.py        # edge-tts synthetic Urdu voice notes
│   ├── degrade_audio.py          # ffmpeg noise mixing at set SNR
│   ├── burst_test.py             # 50 concurrent injections
│   └── baseline_stopwatch.py     # human baseline timing harness
│
├── storage/audio/                # local media, 72h TTL (gitignored)
├── nidaa.db                      # SQLite (gitignored)
└── .env.example
```

**Environment variables**

```
GROQ_API_KEY=
STT_MODEL_PRIMARY=whisper-large-v3-turbo
STT_MODEL_ESCALATION=whisper-large-v3
LLM_MODEL_PRIMARY=openai/gpt-oss-120b
LLM_MODEL_FALLBACK=qwen/qwen3.6-27b
CORE_URL=http://127.0.0.1:8000
INGEST_URL=http://127.0.0.1:3000
STT_RATE_LIMIT_RPM=15
LLM_RATE_LIMIT_RPM=25
WORKER_CONCURRENCY=6
AUDIO_TTL_HOURS=72
DEMO_MODE=false
```

> **Model note.** Groq has deprecated `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` on the free and developer tiers. Do not build on them. `openai/gpt-oss-120b` is the primary extraction model, with `qwen/qwen3.6-27b` as the fallback. Both support JSON structured output. Verify current model IDs on the Groq console the morning of Day 1, because this list moves.

> **Filename note (post-v1.0.0, added during implementation).** The original layout named this file `core/queue.py`. That shadows Python's own standard-library `queue` module, which `anyio`/`asyncio` import internally — with `core/` on `sys.path` (true whenever you run `uvicorn` from inside that directory), every route breaks with `ImportError: cannot import name 'Queue' from 'queue'`, not just the ones that touch the pipeline queue. Renamed to `core/pipeline_queue.py` everywhere in this doc and the codebase.

---

## 2. Database Schema (SQLite, WAL)

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS consent_ledger (
    sender_hash        TEXT PRIMARY KEY,
    phone_tail         TEXT NOT NULL,             -- last 3 digits only
    state              TEXT NOT NULL DEFAULT 'pending',
                                                  -- pending|granted|revoked
    notice_sent_at     TEXT,
    granted_at         TEXT,
    revoked_at         TEXT,
    purge_after        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    wa_message_id      TEXT UNIQUE,
    sender_hash        TEXT NOT NULL,
    phone_tail         TEXT,
    modality           TEXT NOT NULL,             -- audio|text
    audio_path         TEXT,
    audio_duration_s   REAL,
    raw_text           TEXT,                      -- inbound text, or transcript
    detected_language  TEXT,
    stt_model_used     TEXT,
    stt_avg_logprob    REAL,
    stt_no_speech_prob REAL,
    stt_compression    REAL,
    status             TEXT NOT NULL DEFAULT 'received',
                       -- received|preflight_failed|transcribed
                       -- |audio_unintelligible|extracted|failed
    error_code         TEXT,
    t_received         TEXT NOT NULL,
    t_transcribed      TEXT,
    t_extracted        TEXT,
    t_published        TEXT,
    ttt_ms             INTEGER
);

CREATE TABLE IF NOT EXISTS tickets (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id         INTEGER NOT NULL REFERENCES messages(id),
    intent             TEXT,      -- resource_request|incident_report
                                  -- |infrastructure_damage|non_actionable
    urgency            TEXT,      -- critical|high|moderate|info
    loc_name           TEXT,      -- #loc+name
    adm2_name          TEXT,      -- #adm2+name  (district)
    adm1_name          TEXT,      -- #adm1+name  (province)
    pcode              TEXT,      -- #adm2+code
    latitude           REAL,      -- #geo+lat
    longitude          REAL,      -- #geo+lon
    geocode_method     TEXT,      -- exact|fuzzy|alias|none
    geocode_score      REAL,
    items_json         TEXT,      -- [{"item":"...","qty":20,"unit":"family"}]
    people_affected    INTEGER,
    casualties         INTEGER,
    missing_fields     TEXT,      -- JSON array
    extraction_conf    REAL,
    reasoning_note     TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unconfirmed',
                       -- unconfirmed|user_confirmed|user_disputed
                       -- |dispatcher_verified|dispatcher_rejected
    duplicate_of       INTEGER REFERENCES tickets(id),
    readback_sent_at   TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq                INTEGER PRIMARY KEY AUTOINCREMENT,
    kind               TEXT NOT NULL,   -- ticket.created|ticket.updated
                                        -- |message.status|metrics
    payload            TEXT NOT NULL,   -- JSON
    created_at         TEXT NOT NULL
);

CREATE INDEX idx_tickets_adm2    ON tickets(adm2_name);
CREATE INDEX idx_tickets_urgency ON tickets(urgency);
CREATE INDEX idx_tickets_created ON tickets(created_at);
CREATE INDEX idx_messages_status ON messages(status);
```

`events.seq` is the SSE cursor. Every state change writes exactly one event row inside the same transaction as the data change, which is what makes the reconnect replay correct rather than approximate.

---

## 3. API Contract

### 3.1 Internal (Node daemon to Python core)

```
POST /internal/ingest
Content-Type: application/json

{
  "wa_message_id": "3EB0...",
  "sender_hash": "sha256:...",
  "phone_tail": "417",
  "modality": "audio",
  "audio_path": "/storage/audio/3EB0.wav",
  "audio_duration_s": 14.2,
  "text": null,
  "received_at": "2026-08-28T09:14:02.113Z"
}

202 Accepted
{ "message_id": 481, "queued": true, "queue_depth": 3 }
```

> **Addendum (post-v1.0.0, added during implementation).** The original contract specified `/internal/ingest` but never specified how the Node daemon checks or updates `consent_ledger` before deciding whether to call it — section 6 says "check consent_ledger" without saying by what mechanism, and `nidaa.db` is owned exclusively by `core/` (docs/ARCHITECTURE.md §2.1: no cross-process DB access). Two routes close that gap:

```
POST /internal/consent/check
{ "sender_hash": "sha256:...", "phone_tail": "417" }

200 OK
{ "state": "granted" | "revoked", "send_notice": true }
```
Behaviour: if no ledger row exists yet, core creates one with `state=granted` (first contact is implied consent per PRD §3.1), sets `granted_at`/`notice_sent_at` to now and `purge_after` to now+72h, and returns `send_notice: true` — this is the one time the daemon should send the consent notice. If a row already exists, core returns its current state and `send_notice: false` always (the notice fires once per sender, never again). If `state: "revoked"`, the daemon drops the message silently and never calls `/internal/ingest` for it.

```
POST /internal/consent/revoke
{ "sender_hash": "sha256:..." }

200 OK
{ "ok": true }
```
Behaviour: sets `state=revoked`, `revoked_at=now`, and purges that sender's stored audio files and transcript text from `messages` (PRD §3.1/§3.4). Called by the daemon when it sees `BAND` or `STOP` from a sender, before anything else in the message-handling flow (TRD §6, step 4).

### 3.2 Outbound callback (Python core to Node daemon)

```
POST /internal/reply
{
  "sender_hash": "sha256:...",
  "template": "audio_unintelligible" | "consent_notice"
              | "readback" | "location_missing",
  "vars": { "adm2": "Dadu", "items": "khana aur pani", "urgency": "Emergency" }
}
```

The Node side owns all message text and all send pacing. The Python side never composes user-facing Urdu, which keeps the copy in one file and keeps the rate limiting in one place.

### 3.3 Public (dashboard)

```
GET  /api/tickets?urgency=critical,high&adm2=Dadu&since=12h
GET  /api/metrics          -> { median_ttt_ms, p95_ttt_ms, count,
                                queue_depth, unintelligible_count,
                                human_baseline_ms }
GET  /api/stream           -> text/event-stream (supports Last-Event-ID)
POST /api/tickets/{id}/verdict   { "verdict": "verified" | "rejected" }
GET  /api/export/hxl.csv
POST /api/simulate         -> demo injection, only when DEMO_MODE=true
```

### 3.4 SSE frame format

```
id: 1042
event: ticket.created
data: {"ticket_id":88,"adm2":"Dadu","urgency":"critical",...}
```

Client reconnect: the browser automatically sends `Last-Event-ID`. The server replays `SELECT * FROM events WHERE seq > ? ORDER BY seq` before resuming the live feed. A heartbeat comment (`: ping`) every 15 seconds keeps proxies from closing the stream.

---

## 4. Pipeline Specification

### 4.1 Queue and rate limiting

* Single `asyncio.Queue`, `WORKER_CONCURRENCY` consumers (default 6).
* Two independent token buckets: STT at 15 RPM, LLM at 25 RPM. Both are deliberately set below the documented free-tier ceilings (Whisper on Groq's free tier is 20 RPM, 2,000 RPD, 7,200 audio-seconds per hour).
* A worker acquires a token before every outbound call and awaits if the bucket is empty. Nothing is dropped, only delayed.
* Retries: exponential backoff with jitter, maximum 3 attempts, and on a `429` the bucket refill rate is halved for 60 seconds.
* `queue_depth` is published on the metrics event every 2 seconds so backpressure is visible on the dashboard rather than hidden.

### 4.2 Stage 0, pre-flight (`preflight.py`)

```python
DURATION_MIN_S   = 1.2
DURATION_MAX_S   = 300.0
SILENCE_RMS_DB   = -45.0   # mean_volume from ffmpeg volumedetect
```

Runs `ffprobe` and `ffmpeg -af volumedetect`. Fails fast with `error_code = AUDIO_TOO_SHORT | AUDIO_TOO_LONG | AUDIO_SILENT`. No API quota is spent on a failed pre-flight.

### 4.3 Stage 1, transcription (`stt.py`)

```python
resp = groq.audio.transcriptions.create(
    file=open(path, "rb"),
    model=STT_MODEL_PRIMARY,
    language="ur",                 # hint, not a hard constraint
    response_format="verbose_json",
    temperature=0.0,
)
```

Confidence gate, reject if **any** condition holds:

```python
NO_SPEECH_MAX      = 0.60
AVG_LOGPROB_MIN    = -0.90
COMPRESSION_MAX    = 2.40
MIN_CONTENT_TOKENS = 5
```

`compression_ratio` above 2.4 is the Whisper repetition-loop signature (the same phrase emitted dozens of times) and must be caught, because it produces long, fluent, entirely fake transcripts that an LLM will happily turn into a confident ticket.

**Escalation:** on rejection, retry once with `STT_MODEL_ESCALATION` (`whisper-large-v3`). On a second rejection set `status = audio_unintelligible`, **skip extraction entirely**, publish the ticket row with the orange status, and fire the `audio_unintelligible` reply template.

### 4.4 Stage 2, extraction (`extract.py`)

Request shape:

```python
resp = groq.chat.completions.create(
    model=LLM_MODEL_PRIMARY,
    messages=[{"role":"system","content":SYSTEM_PROMPT},
              {"role":"user","content":transcript}],
    response_format={"type": "json_object"},
    temperature=0.1,
    max_tokens=1200,
)
```

Required output schema:

```json
{
  "records": [
    {
      "intent": "resource_request",
      "urgency": "critical",
      "location_raw": "Dadu ke pass Johi",
      "district_guess": "Dadu",
      "province_guess": "Sindh",
      "items": [{"item": "food", "qty": 20, "unit": "family"}],
      "people_affected": 120,
      "casualties": 0,
      "missing_fields": [],
      "extraction_confidence": 0.86,
      "reasoning_note": "Speaker names Johi town and requests rations."
    }
  ]
}
```

Validation: parse with a Pydantic model. On `ValidationError` or a JSON parse failure, retry once against `LLM_MODEL_FALLBACK`. On a second failure, set `status = failed`, `error_code = EXTRACTION_INVALID`, and surface the row for manual handling. The system never falls back to a partially-parsed guess.

**Hard rules encoded in the prompt:**
1. Output JSON only, no prose, no markdown fences.
2. Never emit latitude or longitude. Coordinates are the geocoder's job.
3. If the location is absent, `location_raw` is `null` and `missing_fields` contains `"location"`.
4. Multiple independent needs produce multiple array entries.
5. `extraction_confidence` must reflect genuine uncertainty. Low confidence is a correct answer.

### 4.5 Stage 3, geocoding (`geocode.py`)

Deterministic, offline, no LLM involvement.

**Gazetteer build (Day 1).** Download the Pakistan COD-AB administrative boundaries tabular data from HDX (`data.humdata.org/dataset/cod-ab-pak`). Flatten admin levels 0 to 3 into `data/pak_gazetteer.csv`:

```
adm1_name,adm1_pcode,adm2_name,adm2_pcode,adm3_name,adm3_pcode,lat,lon
```

Centroids come from the shapefile or, to stay dependency-light, from the gazetteer's own coordinate columns where present.

**Matching cascade:**
1. **Alias lookup.** `data/aliases.json` maps hand-curated Roman Urdu variants for the top 40 flood-affected districts: `{"daadu":"Dadu","dadoo":"Dadu","ڈاڈو":"Dadu","sakkhar":"Sukkur","khairpoor":"Khairpur", ...}`. Method `alias`, score 1.0.
2. **Exact normalised match** after lowercasing, stripping diacritics and collapsing whitespace. Method `exact`, score 1.0.
3. **Fuzzy match** with `rapidfuzz.process.extractOne` using `WRatio`. Accept at score >= 85. Method `fuzzy`.
4. **No match.** `pcode`, `latitude` and `longitude` all stay `NULL`, `geocode_method = none`, ticket routes to the Unlocated Alerts queue, and the `location_missing` reply template fires asking for a WhatsApp live location pin.

Optional Nominatim fallback for named non-administrative places (a village, a bridge, a school) at strictly 1 request per second with a descriptive `User-Agent`, disabled by default so the demo never depends on an external service.

### 4.6 Stage 4, urgency (`urgency.py`)

Blended score so a model quirk cannot silently downgrade a life-threatening message:

```
final_urgency = max(model_urgency, rule_urgency)
```

Rule triggers forcing `critical`: presence of casualty or injury terms, child or elderly plus water-rise terms, medical terms (`dawai`, `zakhmi`, `hospital`, `saans`), and glossary hits such as `halat ghair ha`, `doobne wale hain`, `chhat gir rahi hai`. Taking the maximum means the rules can escalate but never de-escalate.

### 4.7 Stage 5, near-duplicate flag (`dedupe.py`)

No vector database in the MVP. Key on `(adm2_name, intent, normalised_primary_item, 15-minute bucket)`. A collision sets `duplicate_of` on the newer ticket and the dashboard clusters them under one expandable pin. Duplicates are flagged and counted, never deleted, because twelve reports of one bridge is itself a signal about severity.

---

## 5. System Prompt (extraction)

```
You are a humanitarian crisis triage NLP engine for flood response
operations in Pakistan. You convert raw, messy, code-switched Urdu
and Roman Urdu messages into structured relief records.

OUTPUT
Return a single JSON object with one key, "records", whose value is an
array. Output JSON only. No prose. No markdown fences.

RULES
1. One independent need or incident per array entry. If a message
   reports three collapsed bridges in three districts, return three
   entries.
2. NEVER output latitude, longitude, or a P-code. A separate
   deterministic geocoder handles coordinates. Inventing a location
   can send a rescue boat to the wrong district.
3. If no location is stated, set "location_raw" to null and include
   "location" in "missing_fields". Do not infer a location from
   dialect, accent, or plausibility.
4. Set "extraction_confidence" honestly between 0 and 1. Low
   confidence is a correct and useful answer. Do not inflate it.
5. Preserve numbers exactly as stated. If the speaker says "bees
   ghar" record qty 20 with unit "household". If a number is vague
   ("bohat saray log"), leave qty null and note it.
6. intent must be one of: resource_request, incident_report,
   infrastructure_damage, non_actionable.
7. urgency must be one of: critical, high, moderate, info.

URDU AND ROMAN URDU GLOSSARY
"halat ghair ha"            -> critical medical or physical emergency
"paani ghar mein ghus gaya" -> displacement, shelter and evacuation need
"bachay bhookay hain"       -> food request, children present, raise urgency
"chhat gir rahi hai"        -> structural collapse risk, critical
"doobne wale hain"          -> imminent drowning risk, critical
"dawai khatam ho gayi"      -> medical supply request
"raabta nahi ho raha"       -> communications blackout, treat as incident report
"madad chahiye"             -> generic help request, infer specifics from context
"phansay huay hain"         -> people trapped, critical
"bijli nahi hai"            -> infrastructure damage, moderate unless combined
                               with a medical need

SCHEMA
{ "records": [ { "intent": "...", "urgency": "...",
  "location_raw": "...|null", "district_guess": "...|null",
  "province_guess": "...|null",
  "items": [ {"item":"...","qty":0,"unit":"..."} ],
  "people_affected": 0, "casualties": 0,
  "missing_fields": ["..."], "extraction_confidence": 0.0,
  "reasoning_note": "one short sentence" } ] }
```

Keep the glossary in `prompts/glossary.json` and inject it at startup so a non-engineer on the team can extend it without touching Python.

---

## 6. Node Ingestion Daemon

**Connection.** `@whiskeysockets/baileys`, multi-file auth state persisted to `ingest/auth_state/`, pairing-code login preferred over QR for a headless run, automatic reconnect on `DisconnectReason.restartRequired`, hard stop on `loggedOut`.

**Inbound handler (`messages.upsert`):**
1. Ignore `fromMe`, groups (MVP scope is direct messages), and status broadcasts.
2. Compute `sender_hash = sha256(jid + SALT)`, keep the last 3 digits as `phone_tail`.
3. Check `consent_ledger`. If `pending`, send the consent notice, mark `notice_sent_at`, and still process the current message (implied consent on the sender-initiated first contact). If `revoked`, drop silently.
4. Handle the control keywords `BAND`, `STOP`, `1`, `2` before anything else. `1` and `2` route to the readback handler and never enter the triage pipeline.
5. For audio, download the media, convert with `ffmpeg -ar 16000 -ac 1 -c:a pcm_s16le` to keep the payload small and Whisper-friendly, write to `storage/audio/`.
6. POST to `/internal/ingest`.

**Outbound queue.** All replies pass through a single queue with randomised 1.5 to 3.0 second delays and a global cap. This is both good citizenship and the main practical defence against the linked number being flagged. Never send bulk, never message a number that has not messaged first.

**Reply templates** live in `ingest/templates.js`, in Roman Urdu, with the exact copy from PRD sections 3.1, 3.2 and 6.

---

## 7. Dashboard

* **Stack.** `index.html` plus three files. Leaflet from CDN, Tailwind from CDN, no bundler, no build step.
* **Tiles.** OpenStreetMap standard tiles with correct attribution. Cache a small offline tile set for the Sindh and southern Punjab bounding box so the map still renders if the venue wifi collapses.
* **Layers.** Confirmed (solid), unconfirmed (hollow), disputed (red ring), duplicate cluster (numbered), unintelligible (side list, no pin), unlocated (side list, no pin).
* **Filter chips.** Multi-select toggles for urgency, district and time window. Filtering happens client-side over the in-memory ticket array so it is instant and works while disconnected.
* **TTT header.** Median TTT, p95, ticket count, queue depth, and the human baseline for contrast, updated from the `metrics` SSE event.
* **Row detail drawer.** Audio player, raw transcript, extracted JSON, confidence bar, geocode method badge, and the two verdict buttons.
* **HXL export.** CSV where row 1 is human-readable headers and row 2 is the HXL hashtag row:

```
Location,District,Province,P-code,Latitude,Longitude,Item,Quantity,Affected,Urgency
#loc+name,#adm2+name,#adm1+name,#adm2+code,#geo+lat,#geo+lon,#item+desc,#item+num,#affected+num,#severity+urgency
```

---

## 8. Test Harness

| Tool | Purpose |
| :-- | :-- |
| `tools/make_test_audio.py` | Generates synthetic Urdu voice notes with `edge-tts` (free, no API key) using `ur-PK-AsadNeural` and `ur-PK-UzmaNeural`. Used for the 50-message burst test. |
| `tools/degrade_audio.py` | Mixes rain and wind beds over clean samples at defined SNR steps using `ffmpeg amix`. Produces the acoustic degradation ladder. |
| `tools/burst_test.py` | Fires 50 concurrent POSTs to `/internal/ingest`. Asserts zero 5xx, zero SQLite `database is locked`, zero unhandled 429s, and a final row count of exactly 50. |
| `tools/baseline_stopwatch.py` | CLI that plays a gold-set message, waits for the human to type the structured fields, and records elapsed time. Produces `human_baseline_ms`. |

**Gold set.** 25 messages committed to `data/gold_set/`: 15 audio (5 clean, 5 moderate noise, 5 severe) and 10 text. Each has a `label.json` with the correct district, intent, urgency and items. Accuracy is computed as exact district match and intent match against these labels, and the sample size is reported alongside every number.

**Important:** synthetic TTS audio is unrealistically clean. Record at least 8 of the 15 audio samples as real human voice notes on real phones, ideally outdoors, with team members reading from scripts. Accuracy claims based purely on TTS audio would not survive a judge's follow-up question.

---

## 9. Failure and Error Taxonomy

| `error_code` | Stage | Behaviour |
| :-- | :-- | :-- |
| `AUDIO_TOO_SHORT` / `AUDIO_TOO_LONG` / `AUDIO_SILENT` | Pre-flight | Rejected, no quota spent, sender asked to resend |
| `STT_LOW_CONFIDENCE` | Transcription | Escalate once, then `audio_unintelligible` plus WhatsApp fallback |
| `STT_REPETITION_LOOP` | Transcription | Treated as low confidence, never passed to the LLM |
| `EXTRACTION_INVALID` | Extraction | Retry on fallback model, then manual queue |
| `GEOCODE_NO_MATCH` | Geocoding | Null coordinates, Unlocated Alerts queue, live-location request |
| `RATE_LIMITED` | Any API | Backoff with jitter, bucket refill halved for 60s, message stays queued |
| `WA_SESSION_LOST` | Ingestion | Daemon retries reconnect, dashboard shows a red ingestion banner, simulator remains available |

Every code renders as a plain-English badge in the UI. There are no silent failures, which is the whole point.

---

## 10. Demo Resilience Plan

The single highest-probability demo failure is the WhatsApp session, either through a ban, a session expiry, or venue network filtering. Plan accordingly.

1. `DEMO_MODE=true` exposes `POST /api/simulate`, which injects a gold-set message through the identical pipeline. Same code path, same timestamps, same TTT calculation. Nothing about the demo is faked, only the transport is bypassed.
2. A `tools/demo_replay.py` script fires a scripted sequence: one clean voice note, one multi-intent text, one severely degraded audio (to show the orange failure and the automated fallback reply), and one message with no location (to show the grey unlocated pin).
3. Record a 90-second screen capture of the full live WhatsApp flow on Day 5 as an insurance video.
4. Run the entire demo once with the laptop in airplane mode, except for a phone hotspot, on Day 6.

The judges should see a real phone sending a real voice note. But the story must survive if the phone does not cooperate.

---

## 11. Six-Day Build Schedule

| Day | AI pipeline | Ingestion | Frontend | Data and evaluation |
| :-- | :-- | :-- | :-- | :-- |
| 1 | Repo, FastAPI skeleton, DB migrations, Groq smoke test | Baileys connects, QR paired, logs inbound | Static map, mock ticket list | Gazetteer built, gold set recorded, human baseline timed |
| 2 | STT plus extraction working on one file end to end | Media download and conversion, POST to core | SSE client renders live pins | Alias table for top 40 districts |
| 3 | Queue, token bucket, confidence gate, escalation | Consent notice, BAND handling, outbound queue | Filter chips, urgency colours | Degraded audio ladder generated |
| 4 | Multi-intent, glossary, geocoder, urgency rules, dedupe | Readback correction loop, fallback templates | Detail drawer, verdict buttons, TTT header | HXL export validated against the spec |
| 5 | Hardening, retries, error taxonomy | Reconnect handling, ban-safety pacing | Offline tiles, polish, empty states | Burst test, acoustic test, accuracy run |
| 6 | Freeze at noon. Bug fixes only. | Insurance video recorded | Demo rehearsals x3, one fully offline | Deck built around the TTT number |

---

## 12. Definition of Done

The MVP ships when all of the following are demonstrably true on a clean checkout:

1. A voice note sent from a real phone appears as a mapped, HXL-tagged ticket with a measured TTT under 5 seconds at the median.
2. A first-time sender receives the consent notice exactly once, and `BAND` stops all processing and purges their data.
3. A deliberately noise-destroyed voice note produces an orange `AUDIO_UNINTELLIGIBLE` ticket and an automatic Roman Urdu request to type instead, and the LLM is never called on that transcript.
4. A message with no stated location produces a null-coordinate ticket in the Unlocated Alerts queue, with no invented coordinates anywhere in the database.
5. A message listing three districts produces three separate tickets with three separate P-codes.
6. The readback message fires, and replying `2` flips the ticket to disputed and pushes it to the top of the review queue.
7. A 50-message burst completes with zero crashes, zero database locks and zero unhandled rate-limit errors.
8. The browser can be disconnected for 30 seconds and reaches identical state on reconnect.
9. The HXL CSV export opens cleanly and carries a valid hashtag row.
10. The whole demo runs from the simulator with WhatsApp entirely disconnected.
