# FastAPI app: routes + SSE + startup. See docs/TRD.md section 3 for the
# full API contract (frozen after Day 1 — do not change a route shape here
# without updating that doc and telling your teammate).
#
# Status: the full pipeline is wired end to end -- preflight -> stt (gate +
# escalation) -> extract -> geocode -> urgency-blend -> dedupe -> readback
# trigger, through the async worker pool. Gazetteer/aliases/system-prompt
# (with the glossary baked in) are loaded once at startup, not per-message.
# Confidence-gated error taxonomy hardened (CORE-24): STT_REPETITION_LOOP
# vs STT_LOW_CONFIDENCE, RATE_LIMITED on exhausted retries. Dashboard audio
# player support: list_tickets() now joins messages (db.py) and /audio/*
# is a static mount onto storage/audio/, so historical (not just
# just-arrived-via-SSE) tickets can play their source recording.

import asyncio
import base64
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import groq
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

import db
from config import (
    DEMO_MODE, INGEST_URL,
    STT_MODEL_PRIMARY, STT_MODEL_ESCALATION,
    LLM_MODEL_PRIMARY, LLM_MODEL_FALLBACK,
)
from events import replay_since
from pipeline import preflight, stt, geocode, dedupe
from pipeline.extract import extract, load_system_prompt, ExtractionValidationError
from pipeline.urgency import blended_urgency
from pipeline_queue import PipelineQueue, stt_bucket, llm_bucket, call_with_retry

app = FastAPI(title="Nidaa-AI core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dashboard is a static file with no fixed origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves storage/audio/*.wav directly so the dashboard's audio player can
# fetch a ticket's source recording. Resolved from __file__, not cwd, so it
# doesn't depend on whether the process was launched from core/ or the repo
# root (Render's start command isn't guaranteed to `cd core` first).
_AUDIO_DIR = Path(__file__).parent.parent / "storage" / "audio"
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(_AUDIO_DIR)), name="audio")

pipeline_queue: PipelineQueue | None = None
district_index: dict = {}
aliases: dict = {}


@app.on_event("startup")
def on_startup():
    global pipeline_queue, district_index, aliases
    db.init_db()
    # CORE-17/18: load once at startup, not per-message -- re-reading and
    # re-parsing the gazetteer/aliases/prompt files on every single ticket
    # would be wasted I/O on the hot path, same reasoning as
    # extract.load_system_prompt()'s own internal cache.
    aliases = geocode.load_aliases()
    district_index = geocode.build_district_index(geocode.load_gazetteer(), aliases)
    load_system_prompt()
    pipeline_queue = PipelineQueue(handler=_run_pipeline)
    pipeline_queue.start()


@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": DEMO_MODE}


# --- Internal (ingest daemon -> core) --------------------------------------

@app.post("/internal/consent/check")
async def consent_check(request: Request):
    body = await request.json()
    sender_hash = body["sender_hash"]
    phone_tail = body.get("phone_tail", "")
    with db.get_connection() as conn:
        return db.check_consent(conn, sender_hash, phone_tail)


@app.post("/internal/consent/revoke")
async def consent_revoke(request: Request):
    body = await request.json()
    sender_hash = body["sender_hash"]
    with db.get_connection() as conn:
        db.revoke_consent(conn, sender_hash)
    return {"ok": True}


@app.post("/internal/readback-reply")
async def readback_reply(request: Request):
    """CORE-23. See docs/TRD.md section 3.1's readback-reply addendum."""
    body = await request.json()
    sender_hash = body["sender_hash"]
    reply = body.get("reply")
    if reply not in ("1", "2"):
        raise HTTPException(400, "reply must be '1' or '2'")

    with db.get_connection() as conn:
        ticket = db.find_pending_readback_ticket(conn, sender_hash)
        if ticket is None:
            return {"ok": True, "ticket_id": None}
        db.update_verification(conn, ticket["id"], "user_confirmed" if reply == "1" else "user_disputed")

    # Pillar 5 (Ali's diagnosis): a bare "confirmed: true" leaves the sender
    # unable to tell WHICH ticket they just answered when they have more
    # than one pending readback (find_pending_readback_ticket is LIFO, so a
    # confirm/dispute can land on a different report than the one the
    # sender meant). Forwarding district + items lets ingest/'s template
    # say e.g. "Confirmed for Muzaffargarh (20 khana, 20 pani)" instead.
    await _fire_reply(sender_hash, "readback_ack", {
        "confirmed": reply == "1",
        "adm2": ticket["adm2_name"],
        "items": _format_items_for_readback(json.loads(ticket["items_json"] or "[]")),
    })
    return {"ok": True, "ticket_id": ticket["id"]}


READBACK_MIN_CONFIDENCE = 0.6  # judgment call, see the CORE-22 comment below

# Pillar 4 (multi-turn stitching, docs/TRD.md 4.8): how long a
# sender's incomplete ticket stays open to a follow-up with no location of
# its own. 20 minutes was Ali's proposal for the WhatsApp-conversation pace
# this is meant to cover (a dispatcher-style back-and-forth, not a sender
# picking the thread back up hours later).
FOLLOWUP_SESSION_TTL_MINUTES = 20


def _drop_filled_missing_fields(old_missing: list[str], record: dict) -> list[str]:
    """Pillar 4: after folding a follow-up's fields into an open ticket,
    drop any missing_fields entry it just answered. Only "location" is a
    literal, prompt-guaranteed token (prompts/system_extract.txt rule 3) --
    for people_affected/casualties/items the LLM writes free text describing
    what's missing, so this is a best-effort keyword match, not an exact
    removal. Worst case a stale entry lingers in missing_fields; it never
    causes a wrong merge, since merge_into_ticket() itself only ever fills
    a currently-NULL field or appends a new item."""
    still_missing = []
    for field in old_missing:
        f = field.lower()
        if record["people_affected"] is not None and ("people" in f or "affected" in f):
            continue
        if record["casualties"] is not None and "casualt" in f:
            continue
        if record["items"] and "item" in f:
            continue
        still_missing.append(field)
    return still_missing


def _format_items_for_readback(items: list[dict]) -> str:
    """"20 khandano ke liye food, water" style summary for the readback
    template's {items} var -- ingest/templates.js composes the actual
    Roman Urdu sentence around this, core never writes user-facing copy."""
    if not items:
        return ""
    return ", ".join(
        f"{i['qty']} {i.get('unit', '')} {i['item']}".strip() if i.get("qty") else i["item"]
        for i in items
    )


async def _fire_reply(sender_hash: str, template: str, template_vars: dict | None = None):
    """Calls ingest/'s POST /internal/reply (docs/TRD.md 3.2) so it can
    compose and send the actual Roman Urdu text -- core never composes
    user-facing copy itself. Best-effort: if ingest/ isn't reachable (e.g.
    not running during core-only dev/testing), log and move on rather than
    let a notification failure break the pipeline's own status update."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{INGEST_URL}/internal/reply",
                json={"sender_hash": sender_hash, "template": template, "vars": template_vars or {}},
            )
    except Exception as e:
        print(f"[main] could not reach ingest/ to fire '{template}' reply: {e!r}", flush=True)


def _aggregate_segment_metrics(segments: list) -> dict:
    if not segments:
        return {"stt_avg_logprob": None, "stt_no_speech_prob": None, "stt_compression": None}
    return {
        "stt_avg_logprob": sum(s.get("avg_logprob", 0) for s in segments) / len(segments),
        "stt_no_speech_prob": max(s.get("no_speech_prob", 0) for s in segments),
        "stt_compression": max(s.get("compression_ratio", 0) for s in segments),
    }


async def _run_pipeline(message_id: int) -> None:
    """CORE-09/13/14: preflight -> stt (gate + escalation) -> extract, run
    by a PipelineQueue worker. Every exit path updates `messages.status` so
    nothing is left silently stuck at "received" (TRD section 9)."""
    with db.get_connection() as conn:
        msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    sender_hash = msg["sender_hash"]
    t_received = msg["t_received"]
    transcript = msg["raw_text"] or ""

    if msg["modality"] == "audio":
        preflight_result = await asyncio.to_thread(preflight.run_preflight, msg["audio_path"])
        if not preflight_result["ok"]:
            with db.get_connection() as conn:
                db.update_message_status(conn, message_id, "preflight_failed", error_code=preflight_result["error_code"])
            return

        try:
            result = await call_with_retry(stt_bucket, stt.transcribe, msg["audio_path"], model=STT_MODEL_PRIMARY)
            escalated = False
            if not stt.passes_confidence_gate(result):
                escalated = True
                # temperature=0.2 on the retry (Pillar 3): temperature=0.0 is
                # exactly what can lock Whisper into a repetition loop on
                # noisy audio -- a little sampling randomness gives the
                # escalation model a chance to escape one instead of
                # deterministically reproducing the same failure.
                result = await call_with_retry(stt_bucket, stt.transcribe, msg["audio_path"], model=STT_MODEL_ESCALATION, temperature=0.2)
        except groq.APIError:
            # CORE-24: call_with_retry already exhausted 3 attempts with
            # backoff (docs/TRD.md 4.1) -- this is Groq itself being down
            # or persistently rate-limited, not a one-off blip. RATE_LIMITED
            # is the taxonomy's only code for "any API" exhaustion (TRD
            # section 9); this used to fall through to the queue's generic
            # PIPELINE_ERROR catch-all, losing the specific reason.
            with db.get_connection() as conn:
                db.update_message_status(conn, message_id, "failed", error_code="RATE_LIMITED")
            return

        gate_failure = stt.gate_failure_reason(result)
        gate_passed = gate_failure is None
        transcript = result["text"]
        with db.get_connection() as conn:
            db.update_message_status(
                conn, message_id,
                "transcribed" if gate_passed else "audio_unintelligible",
                # CORE-24: distinguishes STT_REPETITION_LOOP from the
                # general STT_LOW_CONFIDENCE (TRD section 9) instead of
                # collapsing every gate failure into one generic code.
                error_code=gate_failure,
                t_transcribed=_now(),
                raw_text=transcript,
                detected_language=result.get("language"),
                stt_model_used=result.get("model"),
                **_aggregate_segment_metrics(result.get("segments") or []),
            )

        if not gate_passed:
            # Hard rule 4 (../CLAUDE.md): a transcript that fails the gate
            # after escalation must NEVER reach extract(). Fire the
            # fallback template and stop here.
            await _fire_reply(sender_hash, "audio_unintelligible")
            return
        # `escalated` is intentionally unused past this point in Day 3 --
        # nothing currently branches on which model ultimately succeeded,
        # it's implicitly recorded via messages.stt_model_used.

    try:
        try:
            extraction = await call_with_retry(llm_bucket, extract, transcript, model=LLM_MODEL_PRIMARY)
        except ExtractionValidationError:
            extraction = await call_with_retry(
                llm_bucket, extract, transcript, model=LLM_MODEL_FALLBACK,
            )
    except ExtractionValidationError:
        with db.get_connection() as conn:
            db.update_message_status(conn, message_id, "failed", error_code="EXTRACTION_INVALID")
        return
    except groq.APIError:
        # CORE-24: same reasoning as the STT try/except above -- retries
        # already exhausted, this is Groq being unavailable, not bad model
        # output (that's ExtractionValidationError, handled separately).
        with db.get_connection() as conn:
            db.update_message_status(conn, message_id, "failed", error_code="RATE_LIMITED")
        return

    t_extracted = _now()
    any_unlocated = False
    with db.get_connection() as conn:
        # Pillar 4 (docs/TRD.md 4.8): a single-record message that
        # names no location of its own is a follow-up candidate. Checked
        # once per message, not per record -- a message with its own
        # location, or multiple records, is unambiguous enough to stand on
        # its own and always creates a fresh ticket.
        merge_target = None
        if len(extraction["records"]) == 1 and not extraction["records"][0]["location_raw"]:
            merge_target = db.find_open_ticket_for_sender(conn, sender_hash, FOLLOWUP_SESSION_TTL_MINUTES)

        for record in extraction["records"]:
            if merge_target is not None:
                final_urgency = blended_urgency(record["urgency"], transcript)
                db.merge_into_ticket(
                    conn, merge_target["id"],
                    people_affected=record["people_affected"],
                    casualties=record["casualties"],
                    new_items=record["items"],
                    urgency=final_urgency,
                    missing_fields=_drop_filled_missing_fields(
                        json.loads(merge_target["missing_fields"] or "[]"), record,
                    ),
                )
                updated = db.get_ticket(conn, merge_target["id"])
                if updated["adm2_name"] is None:
                    any_unlocated = True
                elif record["extraction_confidence"] >= READBACK_MIN_CONFIDENCE:
                    # Re-confirm with the sender now that the ticket changed
                    # -- same template as first contact (CORE-22), so they
                    # see their follow-up landed on the right report.
                    await _fire_reply(sender_hash, "readback", {
                        "adm2": updated["adm2_name"],
                        "province": updated["adm1_name"],
                        "items": _format_items_for_readback(json.loads(updated["items_json"] or "[]")),
                        "urgency": updated["urgency"],
                    })
                continue

            # CORE-18: deterministic geocoding. Only this call may populate
            # adm2_name/adm1_name/pcode/latitude/longitude -- never the LLM
            # (hard rule 3, ../CLAUDE.md). "none" leaves them all NULL.
            geo = geocode.geocode(record["location_raw"], record["district_guess"], district_index, aliases)
            if geo["geocode_method"] == "none":
                any_unlocated = True

            # CORE-19: rules can only escalate the model's urgency, never
            # de-escalate it (docs/TRD.md 4.6).
            final_urgency = blended_urgency(record["urgency"], transcript)

            # CORE-20: only attempt dedup once a ticket has a real district
            # -- adm2_name IS NULL never matches anything in SQL (NULL =
            # NULL is not true), so skipping it for Unlocated tickets isn't
            # a workaround, it's just not paying for a query that could
            # never find a match anyway.
            duplicate_of = None
            if geo["adm2_name"] is not None:
                key = dedupe.bucket_key(
                    geo["adm2_name"], record["intent"],
                    dedupe.primary_item_from_items(record["items"]),
                    datetime.now(timezone.utc),
                )
                duplicate_of = dedupe.find_duplicate(conn, key)

            ticket_id = db.insert_ticket(
                conn, message_id=message_id,
                intent=record["intent"], urgency=final_urgency,
                loc_name=record["location_raw"],
                adm2_name=geo["adm2_name"], adm1_name=geo["adm1_name"], pcode=geo["pcode"],
                latitude=geo["latitude"], longitude=geo["longitude"],
                geocode_method=geo["geocode_method"], geocode_score=geo["geocode_score"],
                items=record["items"],
                people_affected=record["people_affected"],
                casualties=record["casualties"],
                missing_fields=record["missing_fields"],
                extraction_conf=record["extraction_confidence"],
                reasoning_note=record["reasoning_note"],
                duplicate_of=duplicate_of,
            )

            # CORE-22: readback only on medium/high confidence (PRD 3.2).
            # The TRD doesn't give an exact numeric cutoff for "medium" --
            # 0.6 is a judgment call made here, not a value pulled from the
            # spec; worth revisiting once the gold set gives a real sense
            # of the model's confidence distribution.
            if record["extraction_confidence"] >= READBACK_MIN_CONFIDENCE and geo["adm2_name"] is not None:
                db.mark_readback_sent(conn, ticket_id)
                await _fire_reply(sender_hash, "readback", {
                    "adm2": geo["adm2_name"],
                    "province": geo["adm1_name"],
                    "items": _format_items_for_readback(record["items"]),
                    "urgency": final_urgency,
                })
        t_published = _now()
        ttt_ms = int((_parse_iso(t_published) - _parse_iso(t_received)).total_seconds() * 1000)
        db.update_message_status(
            conn, message_id, "extracted",
            t_extracted=t_extracted, t_published=t_published, ttt_ms=ttt_ms,
        )

    if any_unlocated:
        # docs/TRD.md 4.5, GEOCODE_NO_MATCH row in the error taxonomy
        # (section 9): ask the sender for a WhatsApp live-location pin.
        await _fire_reply(sender_hash, "location_missing")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _save_forwarded_audio(audio_filename: str | None, audio_data_b64: str | None) -> str | None:
    """audio_data_b64/audio_filename addendum (docs/TRD.md 3.1, post-v1.0.0):
    ingest/ and core/ can run as separate Render services with separate
    disks, so core saves its own copy of the audio bytes ingest/ forwarded
    rather than trusting ingest's local audio_path to mean anything here.
    Returns the path to hand to the pipeline, or None if nothing was sent
    (text messages, or ingest/core sharing a disk with audio_path already
    valid -- kept as a fallback for that case only)."""
    if not audio_data_b64 or not audio_filename:
        return None
    # Path(...).name strips any directory components -- this endpoint is now
    # a real network boundary (a separate Render service calls it), so the
    # filename from the request body is untrusted input, not an internal value.
    safe_name = Path(audio_filename).name
    dest = _AUDIO_DIR / safe_name
    dest.write_bytes(base64.b64decode(audio_data_b64))
    return str(dest)


@app.post("/internal/ingest")
async def internal_ingest(request: Request):
    body = await request.json()
    t_received = body.get("received_at") or _now()
    audio_path = _save_forwarded_audio(body.get("audio_filename"), body.get("audio_data_b64")) \
        or body.get("audio_path")
    with db.get_connection() as conn:
        message_id = db.insert_message(
            conn,
            wa_message_id=body.get("wa_message_id"),
            sender_hash=body["sender_hash"],
            phone_tail=body.get("phone_tail"),
            modality=body["modality"],
            audio_path=audio_path,
            audio_duration_s=body.get("audio_duration_s"),
            raw_text=body.get("text"),
            received_at=t_received,
        )

    await pipeline_queue.put(message_id)
    return {"message_id": message_id, "queued": True, "queue_depth": pipeline_queue.depth}


# --- Public (dashboard) -----------------------------------------------------

@app.get("/api/tickets")
async def get_tickets(urgency: str | None = None, adm2: str | None = None, since: str | None = None):
    urgency_list = urgency.split(",") if urgency else None
    since_iso = _parse_since(since) if since else None
    with db.get_connection() as conn:
        tickets = db.list_tickets(conn, urgency=urgency_list, adm2=adm2, since_iso=since_iso)
    return {"tickets": tickets}


def _parse_since(since: str) -> str:
    """Accepts "12h", "30m", "2d" per docs/TRD.md 3.3."""
    unit = since[-1]
    amount = int(since[:-1])
    unit_map = {"h": "hours", "m": "minutes", "d": "days"}
    delta = timedelta(**{unit_map[unit]: amount})
    return (datetime.now(timezone.utc) - delta).isoformat()


HUMAN_BASELINE_PATH = Path(__file__).parent.parent / "data" / "human_baseline.json"


def _read_human_baseline_ms() -> int | None:
    """Reads tools/baseline_stopwatch.py's output (DATA-03), if it exists."""
    if not HUMAN_BASELINE_PATH.exists():
        return None
    data = json.loads(HUMAN_BASELINE_PATH.read_text(encoding="utf-8"))
    return data.get("median_ms")


@app.get("/api/metrics")
async def get_metrics():
    with db.get_connection() as conn:
        metrics = db.get_metrics(conn, human_baseline_ms=_read_human_baseline_ms())
    metrics["queue_depth"] = pipeline_queue.depth if pipeline_queue else 0
    return metrics


@app.get("/api/stream")
async def stream(request: Request):
    last_event_id = request.headers.get("last-event-id")
    last_seq = int(last_event_id) if last_event_id else 0

    async def event_generator():
        seq = last_seq
        with db.get_connection() as conn:
            for row in replay_since(conn, seq):
                seq = row["seq"]
                yield {"id": str(row["seq"]), "event": row["kind"], "data": row["payload"]}

        while True:
            if await request.is_disconnected():
                break
            with db.get_connection() as conn:
                rows = replay_since(conn, seq)
            for row in rows:
                seq = row["seq"]
                yield {"id": str(row["seq"]), "event": row["kind"], "data": row["payload"]}
            # CORE-15: queue_depth broadcast every 2s (docs/TRD.md 4.1) so
            # backpressure is visible live. Not persisted to `events` --
            # it's a live snapshot, not part of the replayable ticket
            # history, so it deliberately has no `id` (never replayed).
            depth = pipeline_queue.depth if pipeline_queue else 0
            yield {"event": "metrics", "data": json.dumps({"queue_depth": depth})}
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


@app.post("/api/tickets/{ticket_id}/verdict")
async def post_verdict(ticket_id: int, request: Request):
    body = await request.json()
    verdict = body.get("verdict")
    if verdict not in ("verified", "rejected"):
        raise HTTPException(400, "verdict must be 'verified' or 'rejected'")
    with db.get_connection() as conn:
        if db.get_ticket(conn, ticket_id) is None:
            raise HTTPException(404, "ticket not found")
        db.update_dispatcher_verdict(conn, ticket_id, verdict)
    return {"ok": True}


HXL_HEADER_HUMAN = ["Location", "District", "Province", "P-code", "Latitude", "Longitude", "Item", "Quantity", "Affected", "Urgency"]
HXL_HEADER_TAGS = ["#loc+name", "#adm2+name", "#adm1+name", "#adm2+code", "#geo+lat", "#geo+lon", "#item+desc", "#item+num", "#affected+num", "#severity+urgency"]


@app.get("/api/export/hxl.csv")
async def export_hxl():
    with db.get_connection() as conn:
        tickets = db.list_tickets(conn)

    buf = io.StringIO()
    # Excel has no UTF-8 CSV auto-detection without a BOM -- without this it
    # decodes as the system's ANSI codepage instead, turning every Urdu
    # location_raw/loc_name into mojibake. The BOM itself is invisible in
    # every other consumer (HDX, pandas, a text editor) that already
    # correctly assumes UTF-8.
    buf.write(chr(0xFEFF))
    writer = csv.writer(buf)
    writer.writerow(HXL_HEADER_HUMAN)
    writer.writerow(HXL_HEADER_TAGS)
    for t in tickets:
        items = json.loads(t["items_json"] or "[]")
        if not items:
            items = [{"item": "", "qty": ""}]
        for item in items:
            writer.writerow([
                t["loc_name"], t["adm2_name"], t["adm1_name"], t["pcode"],
                t["latitude"], t["longitude"], item.get("item", ""),
                item.get("qty", ""), t["people_affected"], t["urgency"],
            ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=nidaa_tickets_hxl.csv"},
    )


DEFAULT_SIMULATE_TEXT = "Dadu mein bees gharon ke liye khana aur pani chahiye, halat ghair ha."


@app.post("/api/simulate")
async def simulate(request: Request):
    if not DEMO_MODE:
        raise HTTPException(403, "DEMO_MODE is disabled")
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass  # empty body is fine -- uses the default text below
    text = body.get("text") or DEFAULT_SIMULATE_TEXT
    t_received = _now()

    # messages.sender_hash has an enforced FK to consent_ledger (docs/TRD.md
    # section 2 integrity note) -- ensure a ledger row exists first.
    with db.get_connection() as conn:
        db.check_consent(conn, "sha256:simulated", "000")
        message_id = db.insert_message(
            conn, wa_message_id=f"sim-{datetime.now().timestamp()}",
            sender_hash="sha256:simulated", phone_tail="000",
            modality="text", raw_text=text, received_at=t_received,
        )

    # TRD section 10: "nothing about the demo is faked, only the transport
    # is bypassed" -- goes through the exact same queue + worker pool as a
    # real /internal/ingest call (Day 3), not a shortcut around it. The
    # ticket isn't back yet by the time this responds -- watch /api/stream.
    await pipeline_queue.put(message_id)
    return {"message_id": message_id, "queued": True, "queue_depth": pipeline_queue.depth}
