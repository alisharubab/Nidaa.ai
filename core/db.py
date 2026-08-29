# SQLite connection + schema. DDL is frozen per docs/TRD.md section 2 — do not
# change a column here without updating that doc and telling your teammate.

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from config import DB_PATH, AUDIO_TTL_HOURS
from events import append_event

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS consent_ledger (
    sender_hash        TEXT PRIMARY KEY,
    phone_tail         TEXT NOT NULL,
    state              TEXT NOT NULL DEFAULT 'pending',
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
    modality           TEXT NOT NULL,
    audio_path         TEXT,
    audio_duration_s   REAL,
    raw_text           TEXT,
    detected_language  TEXT,
    stt_model_used     TEXT,
    stt_avg_logprob    REAL,
    stt_no_speech_prob REAL,
    stt_compression    REAL,
    status             TEXT NOT NULL DEFAULT 'received',
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
    intent             TEXT,
    urgency            TEXT,
    loc_name           TEXT,
    adm2_name          TEXT,
    adm1_name          TEXT,
    pcode              TEXT,
    latitude           REAL,
    longitude          REAL,
    geocode_method     TEXT,
    geocode_score      REAL,
    items_json         TEXT,
    people_affected    INTEGER,
    casualties         INTEGER,
    missing_fields     TEXT,
    extraction_conf    REAL,
    reasoning_note     TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unconfirmed',
    duplicate_of       INTEGER REFERENCES tickets(id),
    readback_sent_at   TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq                INTEGER PRIMARY KEY AUTOINCREMENT,
    kind               TEXT NOT NULL,
    payload            TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_adm2    ON tickets(adm2_name);
CREATE INDEX IF NOT EXISTS idx_tickets_urgency ON tickets(urgency);
CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
"""


def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Consent (see docs/TRD.md section 3.1 addendum) ------------------------

def check_consent(conn, sender_hash: str, phone_tail: str) -> dict:
    """Upserts the consent ledger row for a sender. First contact is implied
    consent (PRD 3.1): creates the row as `granted` and signals the caller
    to send the one-time notice. Returns {"state": ..., "send_notice": bool}."""
    row = conn.execute(
        "SELECT state FROM consent_ledger WHERE sender_hash = ?", (sender_hash,)
    ).fetchone()
    if row is not None:
        return {"state": row["state"], "send_notice": False}

    now = _now()
    purge_after = (datetime.now(timezone.utc) + timedelta(hours=AUDIO_TTL_HOURS)).isoformat()
    conn.execute(
        """INSERT INTO consent_ledger
           (sender_hash, phone_tail, state, notice_sent_at, granted_at, purge_after)
           VALUES (?, ?, 'granted', ?, ?, ?)""",
        (sender_hash, phone_tail, now, now, purge_after),
    )
    conn.commit()
    return {"state": "granted", "send_notice": True}


def revoke_consent(conn, sender_hash: str) -> None:
    """Sets revoked, then purges that sender's stored audio path + transcript
    text from every message row (PRD 3.1/3.4). Does not delete the row
    itself -- keeping error-free auditability of "this sender was purged"
    is more useful than a silent delete."""
    now = _now()
    conn.execute(
        "UPDATE consent_ledger SET state='revoked', revoked_at=? WHERE sender_hash=?",
        (now, sender_hash),
    )
    conn.execute(
        "UPDATE messages SET audio_path=NULL, raw_text=NULL WHERE sender_hash=?",
        (sender_hash,),
    )
    conn.commit()
    # TODO(ING-06 pairing task): the actual audio *file* on disk under
    # storage/audio/ also needs deleting here, not just the DB pointer to it.


# --- Messages ----------------------------------------------------------------

def insert_message(conn, *, wa_message_id, sender_hash, phone_tail, modality,
                    audio_path=None, audio_duration_s=None, raw_text=None,
                    received_at=None) -> int:
    t_received = received_at or _now()
    cur = conn.execute(
        """INSERT INTO messages
           (wa_message_id, sender_hash, phone_tail, modality, audio_path,
            audio_duration_s, raw_text, status, t_received)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'received', ?)""",
        (wa_message_id, sender_hash, phone_tail, modality, audio_path,
         audio_duration_s, raw_text, t_received),
    )
    message_id = cur.lastrowid
    append_event(conn, "message.status", {"message_id": message_id, "status": "received"})
    conn.commit()
    return message_id


def update_message_status(conn, message_id: int, status: str, *, error_code=None, **timestamps) -> None:
    """timestamps: any of t_transcribed / t_extracted / t_published (ISO
    strings), plus ttt_ms once t_published is known. Emits a message.status
    event in the same transaction."""
    fields = ["status = ?"]
    values = [status]
    if error_code is not None:
        fields.append("error_code = ?")
        values.append(error_code)
    for key, value in timestamps.items():
        fields.append(f"{key} = ?")
        values.append(value)
    values.append(message_id)
    conn.execute(f"UPDATE messages SET {', '.join(fields)} WHERE id = ?", values)
    append_event(conn, "message.status", {"message_id": message_id, "status": status, "error_code": error_code})
    conn.commit()


# --- Tickets -------------------------------------------------------------

def insert_ticket(conn, *, message_id, intent=None, urgency=None, loc_name=None,
                   adm2_name=None, adm1_name=None, pcode=None, latitude=None,
                   longitude=None, geocode_method=None, geocode_score=None,
                   items=None, people_affected=None, casualties=None,
                   missing_fields=None, extraction_conf=None, reasoning_note=None,
                   duplicate_of=None) -> int:
    cur = conn.execute(
        """INSERT INTO tickets
           (message_id, intent, urgency, loc_name, adm2_name, adm1_name, pcode,
            latitude, longitude, geocode_method, geocode_score, items_json,
            people_affected, casualties, missing_fields, extraction_conf,
            reasoning_note, duplicate_of, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (message_id, intent, urgency, loc_name, adm2_name, adm1_name, pcode,
         latitude, longitude, geocode_method, geocode_score,
         json.dumps(items or []), people_affected, casualties,
         json.dumps(missing_fields or []), extraction_conf, reasoning_note,
         duplicate_of, _now()),
    )
    ticket_id = cur.lastrowid
    append_event(conn, "ticket.created", get_ticket(conn, ticket_id))
    conn.commit()
    return ticket_id


def update_verification(conn, ticket_id: int, verification_status: str) -> None:
    conn.execute(
        "UPDATE tickets SET verification_status = ? WHERE id = ?",
        (verification_status, ticket_id),
    )
    append_event(conn, "ticket.updated", get_ticket(conn, ticket_id))
    conn.commit()


def get_ticket(conn, ticket_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else None


def list_tickets(conn, *, urgency: list[str] | None = None, adm2: str | None = None,
                  since_iso: str | None = None) -> list[dict]:
    query = "SELECT * FROM tickets WHERE 1=1"
    params: list = []
    if urgency:
        query += f" AND urgency IN ({','.join('?' * len(urgency))})"
        params.extend(urgency)
    if adm2:
        query += " AND adm2_name = ?"
        params.append(adm2)
    if since_iso:
        query += " AND created_at >= ?"
        params.append(since_iso)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# --- Metrics ---------------------------------------------------------------

def get_metrics(conn, human_baseline_ms: int | None = None) -> dict:
    ttts = [
        r["ttt_ms"]
        for r in conn.execute("SELECT ttt_ms FROM messages WHERE ttt_ms IS NOT NULL").fetchall()
    ]
    ttts.sort()
    count = len(ttts)
    median_ttt_ms = ttts[count // 2] if count else None
    p95_ttt_ms = ttts[int(count * 0.95)] if count else None
    unintelligible_count = conn.execute(
        "SELECT COUNT(*) AS c FROM messages WHERE status = 'audio_unintelligible'"
    ).fetchone()["c"]
    return {
        "median_ttt_ms": median_ttt_ms,
        "p95_ttt_ms": p95_ttt_ms,
        "count": count,
        "queue_depth": 0,  # TODO(CORE-15): wire to the live PipelineQueue.depth
        "unintelligible_count": unintelligible_count,
        "human_baseline_ms": human_baseline_ms,
    }
