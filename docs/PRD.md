# Product Requirements Document (PRD)

**Project Name:** Nidaa-AI (Automated Multi-Modal Crisis Triage Engine)
**Document Version:** 4.0.0 (FINAL, submission build)
**Target Delivery Window:** 6-Day Sprint (MVP Core)
**Primary Track:** Urdu & Regional Language Tech / Humanitarian Open Innovation
**Cost Envelope:** PKR 0. Every runtime dependency runs on a permanent free tier or on the team's own laptops.

---

## 0. One-Line Pitch

> Nidaa-AI turns a stranded person's WhatsApp voice note, recorded in the Urdu they actually speak, into a verified, HXL-tagged, map-pinned relief ticket in under five seconds, and it tells the dispatcher out loud when it is not sure.

**Track winning signals, stated plainly:**
* **Urdu & Regional Language Tech:** people feel understood in the language they actually use. Nidaa-AI never asks a flood victim to switch to English, to type, or to fill a form. It accepts the exact artifact they already produce under stress: a panicked voice note in code-switched Urdu.
* **Open Innovation:** the novelty is clear, useful, and supported by a credible path to execution. The novelty is not "we called an LLM." It is the closed consent-and-correction loop plus the refusal-to-guess geocoder, both of which are running code in the MVP, not roadmap slides.

---

## 1. Problem Space

### 1.1 Context
During extreme climate events in Pakistan (riverine floods, urban flooding, GLOF events), official emergency phone lines saturate within hours. The overflow does not disappear. It migrates to WhatsApp, where grassroots volunteers, local rescue workers and stranded families communicate through rapid voice notes and fragmented text.

### 1.2 The Bottleneck
* **Orthographic and dialectal chaos.** Messages arrive in localized dialects or in unstandardized Roman Urdu, where a single district name has a dozen spellings ("Dadu", "Daadu", "ڈاڈو", "daddu").
* **Audio trapping.** The logistically critical facts (where, how many, what is needed, who is injured) are locked inside audio containers that only a human ear can open.
* **Manual triage failure.** A dispatcher must play each file, decode the dialect, guess the location, cross-reference a map, and retype the record into a spreadsheet. The result is a per-ticket handling cost of several minutes and a queue lag measured in hours.

### 1.3 The Solution
An automated WhatsApp ingestion listener, multilingual speech transcription with an explicit confidence gate, structured LLM entity extraction mapped to UN OCHA HXL standards, deterministic offline P-code geocoding, and a real-time dispatcher command dashboard. Crucially, the system is designed to be **loudly uncertain**: it flags what it could not hear, refuses to invent coordinates, and asks the sender to confirm what it understood.

---

## 2. North Star Metric (the one measurable outcome)

Everything else in this document is subordinate to a single number.

> ### PRIMARY METRIC: **Time-to-Triage (TTT)**
> Elapsed wall-clock time from WhatsApp message receipt to a structured, HXL-tagged, map-visible ticket on the dispatcher dashboard.
>
> **Target: median TTT under 5.0 seconds. Baseline: human dispatcher median, measured by us, on the identical message set.**

### 2.1 How we prove it
1. **We measure our own baseline first.** Before building, one team member acts as a dispatcher: listens to the 25-message evaluation set with headphones, identifies the location, and types the record into a Google Sheet. We stopwatch every ticket. This produces an honest, self-collected human baseline (expected range: 90 to 300 seconds per ticket) instead of a number pulled from a blog post.
2. **The system timestamps itself.** Every record stores `t_received`, `t_transcribed`, `t_extracted`, `t_geocoded`, `t_published`. TTT is `t_published - t_received`, computed in the database, not estimated.
3. **The dashboard displays it live.** A header counter shows median TTT and the running human-baseline comparison. During the demo the judges watch the number update as messages land. The metric is the demo.

### 2.2 Supporting metrics (secondary, reported honestly, never headlined)
| # | Metric | Target | Why it is secondary |
| :-- | :-- | :-- | :-- |
| S1 | District extraction accuracy vs. human-labelled gold set | >= 90% on the 25-message set | Small sample. We report it with the sample size attached, not as a general claim. |
| S2 | Concurrency resilience | 0 crashes, 0 DB locks, 0 rate-limit failures on a 50-message burst | Infrastructure hygiene, not user value. |
| S3 | Standards compliance | 100% of exported rows carry valid HXL hashtags and a resolved or explicitly-null P-code | Interoperability proof for NGO partners. |
| S4 | Honest-uncertainty rate | 100% of low-confidence audio surfaces as `AUDIO_UNINTELLIGIBLE`, never as a confident ticket | This is a safety metric. A miss here is worse than a slow ticket. |

---

## 3. Consent, Boundaries and Harmful Misunderstanding

This section exists because a triage system that quietly misreads a distress call is more dangerous than no system at all. Every item below is implemented in the MVP.

### 3.1 First-contact consent notice (automated)
The first time an unknown number messages the triage line, the ingestion daemon replies before any AI processing begins:

```
Nidaa-AI (Rescue Triage Bot)

Ye ek automated rescue triage system hai. Aap ka message AI
se process hoga taake rescue team tak jaldi pohnche.

• Aap ka message aur voice note process kiya jayega
• Aap ka number sirf rescue team ko dikhega (masked)
• Data 72 ghantay baad delete ho jata hai
• Ye AI hai, insan nahi. Ghalti mumkin hai.
• Rukne ke liye likhein: BAND

Emergency? Rescue 1122 / 1129 par call bhi karein.
```

* Consent state is stored per sender in a `consent_ledger` table (`pending`, `granted`, `revoked`).
* Sending any subsequent message constitutes implied consent to process. Replying `BAND` or `STOP` sets `revoked`, purges that sender's stored audio and transcript, and stops all further processing from that number.
* The notice is sent **once per sender**, not per message, so the loop never spams a person in a crisis.
* The bot never claims to be a rescue service. It always points to the real emergency numbers.

### 3.2 The correction loop (our anti-misunderstanding mechanism)
This is the feature that most directly satisfies "test for harmful misunderstandings," and it is the single most differentiating piece of the product.

After extraction, and only when confidence is medium or high, the system sends the sender a plain-language readback of what it understood:

```
Nidaa-AI ne ye samjha hai:

Jagah: Dadu, Sindh
Zaroorat: 20 khandano ke liye khana aur peene ka pani
Halat: Emergency (foran)

Sahi hai? Jawab dein:
1 = Haan, sahi hai
2 = Nahi, ghalat hai
```

* A `1` sets `verification_status = user_confirmed` and the ticket's map pin turns solid.
* A `2` sets `user_disputed`, strips the pin from the confident layer, and pushes the ticket to the top of the dispatcher's manual review queue with a red banner.
* No reply within the demo window leaves it `unconfirmed`, rendered as a hollow pin.

This converts an invisible AI error into a visible, sender-owned correction. It is also the honest answer to "how do you know the AI understood?" The answer is: we asked the person.

### 3.3 Boundaries made visible in the product
| Boundary | How the UI shows it |
| :-- | :-- |
| The AI is a suggestion engine, not a dispatcher | No ticket auto-dispatches anything. Every row requires a human `Acknowledge` click. |
| Transcription may be wrong | The raw audio player sits next to every transcript. One click, headphones on, verify yourself. |
| The AI cannot hear this file | Bright orange `AUDIO_UNINTELLIGIBLE` status, extraction skipped entirely. |
| The AI does not know where this is | Hollow grey pin in a separate "Unlocated Alerts" queue. Never a default coordinate. |
| The AI cannot tell truth from prank | Every ticket carries a `verification_status` field. Nothing is presented as verified fact. |

### 3.4 Data minimisation
* Phone numbers are stored as a SHA-256 hash plus the last three digits for dispatcher callback identification (`***-***-4417`).
* Audio buffers are stored locally, never uploaded anywhere except the transcription endpoint, and are deleted on a 72-hour timer.
* No message content is used for model training. The inference providers used are configured for zero data retention where the free tier offers it.
* Demo data: all voice notes used in the demo are recorded by team members or generated synthetically. No real distress message from a real flood victim is replayed on stage. If a real archived message is ever used, it is used with documented consent and with names and numbers redacted.

---

## 4. User Personas

| Persona | Environment | Core Pain | System Interaction |
| :-- | :-- | :-- | :-- |
| **Ground volunteer / stranded citizen** | Mobile WhatsApp, low bandwidth, high stress, possibly one hand free | Cannot format data, cannot fill a form, can only hold a button and talk | Sends a voice note or a hurried text. Receives a consent notice, a readback confirmation, and a status update. Never leaves WhatsApp. |
| **Command centre dispatcher** | Desktop, dual monitor, stable connection | Drowning in chat notifications, no unified situational picture, no way to prioritise | Works the live map and triage table. Filters by urgency, district and time window. Acknowledges, verifies or rejects each ticket. |
| **Logistics lead / NGO partner** | Field office, intermittent connection | Needs structured supply totals ("rations required in Dadu vs Sukkur") in a format their existing tools ingest | Reads aggregated district-level metrics, exports an HXL-compliant CSV that drops straight into their existing humanitarian pipeline. |

---

## 5. System Architecture (MVP)

```
  WhatsApp user
       |
       v
 [ Node.js ingestion daemon ]  Baileys, multi-device socket
   - consent gate
   - media download to ./storage/audio
   - outbound reply queue (human-paced)
       |  HTTP POST /internal/ingest
       v
 [ Python FastAPI core ]
   - async worker pool + token-bucket limiter
   - Stage 1: pre-flight audio check (ffprobe: duration, RMS)
   - Stage 2: STT  (Whisper Large v3 Turbo, free tier)
   - Stage 3: confidence gate  -> AUDIO_UNINTELLIGIBLE fork
   - Stage 4: LLM extraction (structured JSON, multi-intent array)
   - Stage 5: deterministic geocoder (offline HXL P-code gazetteer)
   - Stage 6: urgency scoring + near-duplicate flag
       |
       v
 [ SQLite (WAL mode) ]  ---> [ SSE /api/stream ] ---> [ Leaflet dashboard ]
```

### 5.1 Verified free-tier component choices

| Layer | Choice | Why, and the free-tier reality (verified Aug 2026) |
| :-- | :-- | :-- |
| Ingestion | Baileys (`@whiskeysockets/baileys`), Node 20+ | Free, browserless, MIT. **Known risk:** automating a personal account breaches WhatsApp ToS and the number can be banned without warning. Mitigation in section 10. |
| Transcription | Groq `whisper-large-v3-turbo` | Free tier: 20 requests/min, 2,000 requests/day, 7,200 audio-seconds/hour, 25 MB max file. Roughly 228x real-time, so a 30-second voice note returns in well under a second. |
| Transcription escalation | Groq `whisper-large-v3` | Used once, only when Turbo returns low confidence, before declaring the audio unintelligible. Slower and more accurate. |
| Extraction LLM | Groq `openai/gpt-oss-120b` (primary), `qwen/qwen3.6-27b` (fallback) | **Important correction to v3.0 of this PRD:** Groq has deprecated `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` on the free and developer tiers. Building on Llama 3 would ship a dead dependency. The GPT-OSS models support JSON structured outputs, which we need. |
| Geocoding | Offline gazetteer built from the HDX OCHA COD-AB Pakistan admin 0-3 P-code tables, plus `rapidfuzz` matching | Zero network calls, zero cost, zero hallucination, and it produces real P-codes rather than invented ones. Optional Nominatim fallback at 1 request/second for named non-administrative places. |
| Database | SQLite in WAL mode | Concurrent dashboard reads while workers write. No server to provision. |
| API | FastAPI + `sse-starlette` | Async, native SSE, single process. |
| Frontend | Zero-build single page: vanilla JS + Leaflet + Tailwind via CDN, OpenStreetMap tiles | No bundler, no `npm run build` failing at 3am on demo day. Loads from `file://` if the venue network dies. |
| Test audio | Microsoft `edge-tts` (free, no key, `ur-PK-AsadNeural` and `ur-PK-UzmaNeural`), plus real recordings from team members | Free synthetic Urdu voice notes for the burst test. Real human recordings for the honest accuracy set, since TTS audio is unrealistically clean. |
| Noise augmentation | `ffmpeg` + freely licensed rain and wind samples | Lets us actually prove the acoustic degradation path instead of describing it. |

### 5.2 Concurrency control
An in-memory `asyncio` queue with a fixed worker pool, fronted by a token-bucket limiter tuned **below** the documented free-tier ceilings: 15 requests per minute against a 20 RPM Whisper limit, and a separate bucket for the LLM. Backpressure is visible: the dashboard shows queue depth live, so a judge asking "what happens at 200 messages" can see the answer on screen rather than hear a claim.

---

## 6. Acoustic Degradation Strategy

A voice note recorded during a downpour, into a cheap microphone, by someone shouting, is the normal case in a disaster zone, not the edge case. We handle it with software logic rather than audio engineering, because six days.

### Stage 0: Pre-flight rejection (free, no API call)
`ffprobe` checks duration and mean volume before the file ever costs us a request:
* Duration under 1.2 seconds, or over 300 seconds: reject.
* Mean RMS below the silence threshold: reject as `AUDIO_SILENT`.

This protects the daily quota from butt-dials and accidental sends.

### Stage 1: Confidence gate on the transcript
The transcription request uses `response_format=verbose_json`, which returns per-segment `avg_logprob`, `no_speech_prob` and `compression_ratio`. The gate rejects a transcript if **any** of:
* `no_speech_prob > 0.6` on the dominant segment
* mean `avg_logprob < -0.9`
* `compression_ratio > 2.4` (the classic Whisper repetition-loop signature, where it outputs the same phrase forty times)
* fewer than 5 tokens of actual content

### Stage 2: One escalation, then honesty
A failed transcript is retried exactly once against the larger `whisper-large-v3` model. If it fails again, the pipeline **skips LLM extraction entirely**. Sending garbage into a language model produces confident, fluent, completely fabricated tickets, which is the worst possible failure mode for a rescue tool.

### Stage 3: Visible failure plus bidirectional recovery
* The record lands on the dashboard with status `AUDIO_UNINTELLIGIBLE`, a bright orange badge, the raw audio player, and the text "AI could not hear this. Listen manually."
* The Node daemon fires an automatic reply to the sender:

```
Nidaa-AI: Awaz saaf nahi aa rahi (background shor bohat zyada hai).
Baraye meherbani apna message TYPE kar ke bhejein, ya WhatsApp
ki LIVE LOCATION bhejein. Rescue team ko itni maloomat chahiye:
jagah, kitne log, kya chahiye.
```

This is the moment the system stops pretending and asks a human for help, in the sender's own language. It is also the most quotable thirty seconds of the demo.

---

## 7. Extraction Engine and Language Handling

### 7.1 Strategy
Zero-shot structured parsing with a strict JSON schema, a localized idiom glossary, and hard anti-hallucination rules.

### 7.2 System prompt pillars
1. **Role.** Humanitarian crisis triage NLP engine for Pakistan flood operations. Output JSON only.
2. **Multi-intent.** A single forwarded message listing three collapsed bridges in three districts must produce an array of three independent records, not one blurred record.
3. **Idiom glossary.** Regional expressions are pre-mapped so the model does not treat them as noise. For example `halat ghair ha` maps to a critical medical or physical emergency, `paani ghar mein ghus gaya` maps to a displacement or shelter need, `bachay bhookay hain` maps to a food request with a child-presence flag.
4. **Refuse to guess.** If the location is absent, `location` must be `null` and `missing_fields` must include `"location"`. The model is explicitly forbidden from emitting coordinates. Coordinates come from the deterministic geocoder only.
5. **Uncertainty is a field.** The model returns `extraction_confidence` between 0 and 1 and a short `reasoning_note`, both surfaced in the dispatcher UI.

### 7.3 Language scope, stated honestly
Whisper's quality varies enormously across the languages this document names. We scope accordingly and say so out loud:

| Language | MVP status |
| :-- | :-- |
| Urdu (script) | Supported, primary target |
| Roman Urdu / Urdu-English code-switch | Supported, primary target |
| Punjabi, Sindhi | Best-effort. Transcription quality drops noticeably. Tickets carry a lower confidence score. |
| Pashto | Best-effort, degraded. |
| Saraiki, Balochi | **Not supported in the MVP.** Whisper has no meaningful training coverage. These messages will route to the manual review queue rather than be silently mistranscribed. |

Overstating dialect coverage is the fastest way to lose credibility with a judge who speaks Saraiki. Understating it and routing those messages to a human is the correct engineering answer and the correct humanitarian one.

---

## 8. Data Model (conceptual)

| Group | Fields |
| :-- | :-- |
| Identity | record id, sender hash, masked phone tail, message id, modality (audio / text), receipt timestamp |
| Consent | consent state, consent timestamp, purge-after timestamp |
| Raw payload | local audio path, raw transcript, detected language, STT model used, STT confidence metrics |
| Classification | intent (`resource_request`, `incident_report`, `infrastructure_damage`, `non_actionable`), urgency (`critical`, `high`, `moderate`, `info`) |
| HXL entities | location name, district (`#adm2`), province (`#adm1`), P-code, latitude, longitude, geocode method, items requested, quantities, people affected count, casualty count |
| State | parsing status, `missing_fields[]`, extraction confidence, verification status (`unconfirmed` / `user_confirmed` / `user_disputed` / `dispatcher_verified` / `dispatcher_rejected`), duplicate-of reference |
| Timing | `t_received`, `t_transcribed`, `t_extracted`, `t_geocoded`, `t_published`, computed `ttt_ms` |

Full DDL is in the TRD.

---

## 9. Dashboard Requirements

* **Zero-build deployment.** Vanilla JS, Leaflet, Tailwind CDN, OpenStreetMap tiles.
* **The TTT header.** Live median Time-to-Triage, ticket count, queue depth, and the human baseline for contrast. This is the first thing a judge sees.
* **Interactive filter chips, not dropdowns.** Multi-select toggles for urgency, district and time window. Toggling instantly re-filters both the table and the map markers with no page reload.
* **Pin semantics carry meaning.** Solid pin = user confirmed. Hollow pin = unconfirmed. Grey pin in the side queue = no location extracted. Orange row = audio unintelligible. Red banner = user disputed the AI's reading.
* **Every row exposes the raw evidence.** Audio player, raw transcript, extracted JSON, and confidence score, all one click away. No black box.
* **Two-click dispatcher verdict.** `Acknowledge` or `Flag as wrong`. Both write to the evaluation table, which is how we generate accuracy numbers from real usage rather than from a spreadsheet.
* **HXL export button.** Downloads a CSV whose second row is the HXL hashtag row, ready for HDX and standard humanitarian tooling.

---

## 10. Interoperability: HXL and P-Codes

| System concept | Standard mapping |
| :-- | :-- |
| Location name | `#loc+name` |
| District | `#adm2+name` |
| Province | `#adm1+name` |
| P-code | `#adm2+code` (Pakistan COD-AB, e.g. `PK6...`) |
| Coordinates | `#geo+lat`, `#geo+lon` |
| Supplies | `#item+desc`, quantity `#item+num` |
| People affected | `#affected+num` |
| Severity | `#severity+urgency`, aligned to OASIS EDXL-CAP `Immediate` / `Expected` / `Future` |

The P-code table is loaded offline from the OCHA Common Operational Dataset for Pakistan. Because the match is deterministic and fuzzy-scored against a real gazetteer, a district either resolves to a genuine P-code or resolves to null. There is no middle state where the system invents an official code.

---

## 11. Edge-Case Mitigation Matrix

| Scenario | Real-world context | Mitigation |
| :-- | :-- | :-- |
| Multi-district demand | One forwarded text lists three collapsing bridges across three cities | Prompt returns an array of distinct records, each geocoded independently |
| Extreme audio noise | Voice note recorded in a downpour | Pre-flight check, confidence gate, model escalation, `AUDIO_UNINTELLIGIBLE`, automated WhatsApp fallback request |
| Localized vernacular | "halat ghair ha" | Idiom glossary primed into the system prompt, mapped to critical urgency |
| Zero geographic context | Emotional distress message with no place named | Location set to null, ticket routed to Unlocated Alerts queue, automated reply requesting a live location pin |
| Spelling drift | "Dadu" / "Daadu" / "ڈاڈو" | Fuzzy match against the gazetteer with a hand-curated alias table for the top 40 flood-affected districts |
| Duplicate reports | Twelve volunteers report the same collapsed bridge | Lightweight near-duplicate flag on (district + intent + item + 15-minute window). Flagged, clustered visually, never auto-deleted |
| Whisper repetition loop | Model outputs the same phrase forty times on noisy input | Compression-ratio gate catches it before extraction |
| Ban or session loss on the WhatsApp number | Baileys session dies mid-demo | Local simulator endpoint replays the identical message set through the identical pipeline. The demo cannot be killed by a network or a ban |
| Prank or false report | Someone reports a fake emergency | Out of scope for the MVP, and we say so. Human dispatcher verdict is the only truth check. |

---

## 12. Testing and Verification Plan

1. **Human baseline run (Day 1).** Stopwatch a team member manually triaging the 25-message evaluation set. This produces the comparison number for the north star metric.
2. **Gold set construction.** 25 messages: 15 audio (5 clean, 5 moderately noisy, 5 severely degraded), 10 text (Roman Urdu, code-switched, multi-intent). Each hand-labelled with the correct district, intent, urgency and item list. This file is the accuracy ground truth and it ships in the repo so judges can inspect it.
3. **Burst test.** 50 messages injected concurrently. Pass criteria: zero crashes, zero SQLite lock errors, zero 429 responses from the inference endpoints, and every message accounted for in the database.
4. **Acoustic degradation test.** The 5 clean samples are re-mixed with rain and wind at increasing gain until the confidence gate trips. We record the signal-to-noise point at which the system correctly gives up. That threshold, honestly reported, is a stronger result than a claimed accuracy percentage.
5. **SSE resilience test.** Kill the browser connection for 30 seconds while messages continue to process. On reconnect the dashboard replays missed events using `Last-Event-ID` and reaches identical state, verified by row count and checksum.
6. **Correction loop test.** Deliberately feed an ambiguous message, confirm the readback fires, reply `2`, and confirm the ticket flips to disputed and jumps the review queue.
7. **Consent test.** Message from a fresh number, confirm the notice fires once and only once. Reply `BAND`, confirm processing stops and stored data for that sender is purged.

---

## 13. Limitations and Risks (stated plainly)

We would rather a judge hear these from us than find them themselves.

**What the MVP cannot do**
1. **It cannot verify truth.** Nidaa-AI has no mechanism to distinguish a genuine emergency from a prank, a rumour, or a duplicate forwarded six times. It structures claims, it does not validate them. Human dispatchers remain the only truth layer.
2. **Transcription degrades badly in real acoustic conditions.** High wind, heavy rain, distant microphones and shouting all push Whisper's accuracy down sharply. Our answer is to detect and declare that failure, not to claim we solved it.
3. **Dialect coverage is uneven.** Saraiki and Balochi are not supported. Sindhi, Punjabi and Pashto are best-effort with measurably lower quality than Urdu. The system routes these to humans rather than guessing.
4. **The WhatsApp integration is unofficial.** Baileys automates a linked device and breaches WhatsApp's terms of service. The number can be banned without warning, and the protocol can break when Meta changes it. Production deployment requires the official WhatsApp Business Cloud API under an NGO or government account, which needs a verified business entity we do not have during a hackathon. We use a dedicated burner SIM, never a personal number, and we ship a simulator so the system is demonstrable without it.
5. **Free-tier ceilings are real.** 20 transcription requests per minute and 2,000 per day. A genuine national flood event would exhaust that within an hour. The architecture is queue-based and provider-agnostic specifically so this becomes a billing decision rather than a rewrite.
6. **Geocoding resolves to district centroid, not to a street.** A P-code plus a centroid gets a rescue boat to the right union council, not to the right rooftop. Rooftop precision requires a WhatsApp live-location pin, which we request but cannot compel.
7. **Small evaluation sample.** Accuracy figures come from a 25-message hand-labelled set. That is enough to demonstrate a working pipeline. It is not enough to claim a production accuracy rate, and we do not.
8. **No security model.** The MVP dashboard has no authentication. Role-based access control is Phase 3, and until it exists this system must not touch real victim data outside a controlled test.

**What still needs validation**
* Accuracy against real, in-the-wild flood-season audio rather than our own recordings.
* Whether dispatchers actually trust the confidence badges or learn to ignore them.
* Whether senders in genuine distress will engage with the `1` / `2` correction loop, or ignore it entirely.
* Field testing with an actual relief foundation before any live deployment.

---

## 14. Team Roles

| Area | Owner | Scope |
| :-- | :-- | :-- |
| **AI pipeline (Python, Groq)** | *[Name]* | FastAPI core, async queue and token bucket, transcription and confidence gate, prompt engineering, extraction schema, urgency scoring |
| **Ingestion hook (Node.js, Baileys)** | *[Name]* | WhatsApp daemon, session management, media download, consent gate, outbound reply queue, correction loop replies |
| **Frontend dashboard (Leaflet)** | *[Name]* | Live map, filter chips, triage table, SSE client with reconnect, TTT header, HXL export |
| **Data, standards and evaluation** | *[Name]* | HDX P-code gazetteer build, fuzzy matcher and alias table, gold evaluation set, human baseline timing, burst and acoustic test harness, pitch deck |

Cross-cutting: schema and API contract are agreed and frozen on Day 1 so the three runtimes can be built in parallel against mocks.

---

## 15. Six-Day Delivery Plan

| Day | Milestone | Exit criterion |
| :-- | :-- | :-- |
| **1** | Contracts and scaffolding | DB schema frozen, API contract frozen, Groq keys live, gazetteer CSV parsed and loaded, human baseline stopwatch run complete |
| **2** | Vertical slice | One hardcoded audio file goes in, one structured row comes out and appears on the map. Ugly but end to end |
| **3** | Real ingestion plus resilience | Baileys live on the burner number, consent notice firing, queue and token bucket in place, confidence gate implemented |
| **4** | Intelligence and standards | Multi-intent extraction, idiom glossary, fuzzy geocoder with P-codes, urgency scoring, HXL export, correction loop live |
| **5** | Polish and proof | Dashboard filter chips, TTT header, burst test, acoustic test, SSE reconnect test, gold set accuracy run |
| **6** | Freeze and rehearse | Feature freeze at noon. Simulator fallback verified. Deck built around the TTT number. Full demo rehearsed three times, once with the network unplugged |

Day 6 has no new features in it. That is deliberate. A rehearsed demo of four working things beats a broken demo of eight.

---

## 16. Roadmap Beyond the MVP

**Phase 2, resilience and automation**
* Semantic deduplication with sentence embeddings to cluster reports of the same incident from different senders.
* Bidirectional follow-up: automatically ping senders for the specific `missing_fields` the extractor flagged.
* Union-council level (`#adm3`) geocoding and live-location pin ingestion.
* Human-correction feedback loop: every dispatcher `Flag as wrong` becomes a few-shot example in the prompt.

**Phase 3, multi-platform and secure scale**
* Migration to the official WhatsApp Business Cloud API under a partner NGO's verified account.
* SMS and GSM gateway fallback for cellular-down and data-down zones.
* Role-based access control separating administrators, dispatchers and NGO observers, plus a full audit log.
* Postgres and PostGIS migration, spatial clustering, and a live 3W (who does what where) feed for OCHA-aligned coordination.

---

## 17. What We Are Actually Claiming

We are not claiming to have built a national emergency system in six days. We are claiming one specific, measured thing:

> A distress voice note in code-switched Urdu becomes a standards-compliant, map-visible, human-verifiable relief ticket in under five seconds instead of several minutes, and when the system cannot understand the message, it says so in the sender's own language and asks for help instead of inventing an answer.

That is one focused proof of concept, one measurable outcome, and a credible path to execution.
