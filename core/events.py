# Append-only event log used as the SSE cursor. See docs/TRD.md section 3.4
# and docs/ARCHITECTURE.md section 6: every state change writes exactly one
# event row inside the same transaction as the data change it describes.

import json
from datetime import datetime, timezone


def append_event(conn, kind: str, payload: dict) -> int:
    """Insert one event row on the given (open, in-transaction) connection.
    Returns the new event's seq. Caller controls the transaction/commit."""
    cur = conn.execute(
        "INSERT INTO events (kind, payload, created_at) VALUES (?, ?, ?)",
        (kind, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
    )
    return cur.lastrowid


def replay_since(conn, last_seq: int = 0):
    """Used on SSE client reconnect via Last-Event-ID: replay every event
    with seq > last_seq, in order, before resuming the live stream."""
    rows = conn.execute(
        "SELECT seq, kind, payload, created_at FROM events WHERE seq > ? ORDER BY seq",
        (last_seq,),
    ).fetchall()
    return rows


# TODO(CORE-10): wire this into a GET /api/stream route using sse-starlette,
# including the `: ping` heartbeat comment every 15s (docs/TRD.md section 3.4).
