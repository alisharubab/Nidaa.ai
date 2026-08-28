# SQLite connection + schema. DDL is frozen per docs/TRD.md section 2 — do not
# change a column here without updating that doc and telling your teammate.

import sqlite3
from contextlib import contextmanager

from config import DB_PATH

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


# TODO(CORE-02): DAO helper functions (insert_message, update_ticket, etc.)
# go here. Every write that should also emit an SSE event must call
# events.append_event(...) inside the SAME transaction/connection — see
# docs/ARCHITECTURE.md section 6.
