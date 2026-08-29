# FastAPI app: routes + SSE + startup. See docs/TRD.md section 3 for the
# full API contract (frozen after Day 1 — do not change a route shape here
# without updating that doc and telling your teammate).
#
# Day-1 status: consent, ingest intake, ticket read/verdict, metrics, and
# HXL export are real and DB-backed. The pipeline itself (preflight -> stt
# -> extract -> geocode -> urgency -> dedupe) is NOT wired in yet -- that's
# Day 2 (CORE-06 through CORE-09). Until then, /internal/ingest records the
# message and leaves it at status=received; nothing publishes a ticket for
# it automatically. /api/simulate exists for exactly this gap: it lets the
# other tracks (ingest, dashboard) develop and test against a real ticket
# end-to-end without the pipeline existing yet.

import asyncio
import csv
import io
import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

import db
from config import DEMO_MODE
from events import replay_since

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


@app.post("/internal/ingest")
async def internal_ingest(request: Request):
    body = await request.json()
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
            received_at=body.get("received_at"),
        )
    # TODO(CORE-09/CORE-11): enqueue message_id onto the PipelineQueue here
    # once pipeline_queue.py's worker loop actually runs the pipeline
    # stages. Today this just records the message at status=received.
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


@app.get("/api/metrics")
async def get_metrics():
    # TODO(DATA-03): wire human_baseline_ms from the tools/baseline_stopwatch.py
    # output once that run has been recorded, instead of None.
    with db.get_connection() as conn:
        return db.get_metrics(conn, human_baseline_ms=None)


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
    status = "dispatcher_verified" if verdict == "verified" else "dispatcher_rejected"
    with db.get_connection() as conn:
        if db.get_ticket(conn, ticket_id) is None:
            raise HTTPException(404, "ticket not found")
        db.update_verification(conn, ticket_id, status)
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


@app.post("/api/simulate")
async def simulate():
    if not DEMO_MODE:
        raise HTTPException(403, "DEMO_MODE is disabled")
    # TODO(CORE-25): replay a real gold-set message through the actual
    # pipeline stages once they exist (Day 2+), rather than inserting a
    # canned ticket directly. Kept minimal today so FE/ING can already test
    # against a real ticket.created SSE event.
    with db.get_connection() as conn:
        message_id = db.insert_message(
            conn, wa_message_id=f"sim-{datetime.now().timestamp()}",
            sender_hash="sha256:simulated", phone_tail="000",
            modality="text", raw_text="[simulated] 20 khandano ke liye khana aur paani chahiye, Dadu mein.",
        )
        ticket_id = db.insert_ticket(
            conn, message_id=message_id, intent="resource_request", urgency="critical",
            loc_name="Dadu", adm2_name="Dadu", adm1_name="Sindh", pcode="PK602",
            latitude=26.7306, longitude=67.7770, geocode_method="alias", geocode_score=1.0,
            items=[{"item": "food", "qty": 20, "unit": "family"}, {"item": "water", "qty": 20, "unit": "family"}],
            people_affected=120, casualties=0, extraction_conf=0.9,
            reasoning_note="Simulated ticket via /api/simulate.",
        )
    return {"message_id": message_id, "ticket_id": ticket_id}
