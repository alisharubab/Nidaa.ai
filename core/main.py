# FastAPI app: routes + SSE + startup. See docs/TRD.md section 3 for the
# full API contract (frozen after Day 1 — do not change a route shape here
# without updating that doc and telling your teammate).

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import DEMO_MODE
from db import init_db

app = FastAPI(title="Nidaa-AI core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dashboard is a static file with no fixed origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    # TODO(CORE-01): load gazetteer (data/pak_gazetteer.csv), aliases
    # (data/aliases.json), and prompts (prompts/system_extract.txt,
    # prompts/glossary.json) into memory once here.


@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": DEMO_MODE}


# --- Internal (ingest daemon -> core) --------------------------------------

@app.post("/internal/ingest")
async def internal_ingest():
    # TODO(CORE-09 / ING-05): accept the payload shape in docs/TRD.md 3.1,
    # write a messages row (t_received = now), enqueue for pipeline
    # processing, return 202 with {message_id, queued, queue_depth}.
    raise NotImplementedError


# --- Public (dashboard) -----------------------------------------------------

@app.get("/api/tickets")
async def get_tickets():
    # TODO(CORE-04): support urgency/adm2/since query params per TRD 3.3.
    raise NotImplementedError


@app.get("/api/metrics")
async def get_metrics():
    # TODO(CORE-04): median_ttt_ms, p95_ttt_ms, count, queue_depth,
    # unintelligible_count, human_baseline_ms.
    raise NotImplementedError


@app.get("/api/stream")
async def stream():
    # TODO(CORE-10): sse-starlette EventSourceResponse, replay events with
    # seq > Last-Event-ID before resuming the live feed, 15s heartbeat.
    raise NotImplementedError


@app.post("/api/tickets/{ticket_id}/verdict")
async def post_verdict(ticket_id: int):
    # TODO: {"verdict": "verified" | "rejected"} -> dispatcher_verified /
    # dispatcher_rejected, emit an event.
    raise NotImplementedError


@app.get("/api/export/hxl.csv")
async def export_hxl():
    # TODO(CORE-21): two-row header per docs/TRD.md section 7.
    raise NotImplementedError


@app.post("/api/simulate")
async def simulate():
    # TODO(CORE-25): only active when DEMO_MODE=true (docs/TRD.md section 10).
    if not DEMO_MODE:
        return {"error": "DEMO_MODE is disabled"}
    raise NotImplementedError
