# FastAPI app: routes + SSE + startup. See docs/TRD.md section 3 for the
# full API contract (frozen after Day 1 — do not change a route shape here
# without updating that doc and telling your teammate).
#
# Day-2 status: preflight -> stt -> extract now run for real, synchronously,
# inline in the /internal/ingest request (see _run_pipeline_sync below).
# Deliberately NOT yet in this synchronous version, all Day 3+ scope:
#   - no queue/worker pool or rate-limit token buckets (CORE-11, Day 3)
#   - no STT confidence gate or escalation (CORE-13/14, Day 3) -- whatever
#     Whisper returns is accepted as-is
#   - no geocoding (CORE-18, Day 4) -- tickets carry location_raw as
#     loc_name only; adm2_name/adm1_name/pcode/latitude/longitude stay NULL
#     until the real geocoder resolves them. That's correct, not missing --
#     see hard rule 3 in ../CLAUDE.md.
#   - no rule-blended urgency (CORE-19, Day 4) -- urgency is the model's
#     raw value
#   - no dedupe (CORE-20, Day 4)
# /api/simulate still exists for injecting a fully-formed ticket (including
# a location) without needing the geocoder that doesn't exist yet.

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

import db
from config import DEMO_MODE
from events import replay_since
from pipeline import preflight, stt
from pipeline.extract import extract_with_fallback, ExtractionValidationError

app = FastAPI(title="Nidaa-AI core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dashboard is a static file with no fixed origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    db.init_db()
    # TODO(CORE-01 remainder): load gazetteer (data/pak_gazetteer.csv),
    # aliases (data/aliases.json), and the extraction prompt into memory
    # once here, when pipeline/geocode.py and pipeline/extract.py are wired
    # into the worker loop (Day 2).


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


def _run_pipeline_sync(message_id: int, t_received: str, modality: str,
                        audio_path: str | None, text: str | None) -> None:
    """CORE-09: preflight -> stt -> extract, synchronously, one message at a
    time (no queue yet -- CORE-11 replaces this call site on Day 3 without
    changing the stage functions themselves). Every exit path updates
    `messages.status` so nothing is left silently stuck at "received"."""
    if modality == "audio":
        result = preflight.run_preflight(audio_path)
        if not result["ok"]:
            with db.get_connection() as conn:
                db.update_message_status(conn, message_id, "preflight_failed", error_code=result["error_code"])
            return

        stt_result = stt.transcribe(audio_path)
        transcript = stt_result["text"]
        segments = stt_result["segments"]
        with db.get_connection() as conn:
            db.update_message_status(
                conn, message_id, "transcribed", t_transcribed=_now(),
                # raw_text = transcript once STT has run (TRD §2: "inbound
                # text, or transcript"). Also persist the confidence signals
                # -- needed for CORE-13's gate on Day 3, and for the
                # dashboard's confidence badge either way; storing them here
                # rather than discarding them after this function returns.
                raw_text=transcript,
                detected_language=stt_result.get("language"),
                stt_model_used=stt_result.get("model"),
                stt_avg_logprob=(sum(s.get("avg_logprob", 0) for s in segments) / len(segments)) if segments else None,
                stt_no_speech_prob=max((s.get("no_speech_prob", 0) for s in segments), default=None),
                stt_compression=max((s.get("compression_ratio", 0) for s in segments), default=None),
            )
        # TODO(CORE-13/14, Day 3): confidence gate + escalation belong here,
        # between transcription and extraction. A transcript that fails the
        # gate twice must set status=audio_unintelligible and return here,
        # WITHOUT calling extract() below -- see hard rule 4 in ../CLAUDE.md.
    else:
        transcript = text or ""

    try:
        extraction = extract_with_fallback(transcript)
    except ExtractionValidationError:
        with db.get_connection() as conn:
            db.update_message_status(conn, message_id, "failed", error_code="EXTRACTION_INVALID")
        return

    t_extracted = _now()
    with db.get_connection() as conn:
        for record in extraction["records"]:
            db.insert_ticket(
                conn, message_id=message_id,
                intent=record["intent"], urgency=record["urgency"],
                loc_name=record["location_raw"],
                # adm2_name/adm1_name/pcode/latitude/longitude intentionally
                # NOT set from district_guess/province_guess here -- those
                # are the LLM's unverified guesses, not a geocoder result.
                # Only pipeline/geocode.py (CORE-18, Day 4) may populate
                # those columns. Until then the ticket correctly sits in
                # the Unlocated state.
                items=record["items"],
                people_affected=record["people_affected"],
                casualties=record["casualties"],
                missing_fields=record["missing_fields"],
                extraction_conf=record["extraction_confidence"],
                reasoning_note=record["reasoning_note"],
            )
        t_published = _now()
        ttt_ms = int((_parse_iso(t_published) - _parse_iso(t_received)).total_seconds() * 1000)
        db.update_message_status(
            conn, message_id, "extracted",
            t_extracted=t_extracted, t_published=t_published, ttt_ms=ttt_ms,
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


@app.post("/internal/ingest")
async def internal_ingest(request: Request):
    body = await request.json()
    t_received = body.get("received_at") or _now()
    with db.get_connection() as conn:
        message_id = db.insert_message(
            conn,
            wa_message_id=body.get("wa_message_id"),
            sender_hash=body["sender_hash"],
            phone_tail=body.get("phone_tail"),
            modality=body["modality"],
            audio_path=body.get("audio_path"),
            audio_duration_s=body.get("audio_duration_s"),
            raw_text=body.get("text"),
            received_at=t_received,
        )

    _run_pipeline_sync(message_id, t_received, body["modality"], body.get("audio_path"), body.get("text"))

    # Response shape is the frozen TRD 3.1 contract regardless of the fact
    # that processing already happened synchronously above by the time we
    # respond -- "queued"/"queue_depth" become literally accurate once
    # CORE-11's real queue replaces _run_pipeline_sync's direct call.
    return {"message_id": message_id, "queued": True, "queue_depth": 0}


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
    from datetime import timedelta
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
        return db.get_metrics(conn, human_baseline_ms=_read_human_baseline_ms())


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
            yield {"comment": "ping"}
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
    # is bypassed" -- runs through the exact same _run_pipeline_sync used by
    # /internal/ingest (CORE-09), not a canned/fabricated ticket. Since
    # pipeline/geocode.py doesn't exist yet (CORE-18, Day 4), simulated
    # tickets correctly land Unlocated until then -- that's honest, not a
    # regression from the old hardcoded-Dadu-with-coordinates version.
    _run_pipeline_sync(message_id, t_received, "text", None, text)

    with db.get_connection() as conn:
        tickets = conn.execute(
            "SELECT id FROM tickets WHERE message_id = ?", (message_id,)
        ).fetchall()
    return {"message_id": message_id, "ticket_ids": [t["id"] for t in tickets]}
