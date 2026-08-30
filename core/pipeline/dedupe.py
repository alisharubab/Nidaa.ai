# Stage 5: near-duplicate flagging. docs/TRD.md section 4.7.
# No vector DB in the MVP. Key on (adm2_name, intent, normalised_primary_item,
# 15-minute bucket). Duplicates are flagged and counted, never deleted --
# twelve reports of one bridge is itself a signal about severity.

import json
from datetime import datetime, timedelta

BUCKET_MINUTES = 15


def primary_item_from_items(items: list[dict]) -> str:
    """The first item's normalised name, or "" if there are none (an
    incident_report with no requested items still gets a consistent,
    comparable dedupe key -- just one keyed on the empty string)."""
    if not items:
        return ""
    return (items[0].get("item") or "").strip().lower()


def bucket_key(adm2_name: str, intent: str, primary_item: str, created_at: datetime) -> tuple:
    bucket = created_at.replace(
        minute=(created_at.minute // BUCKET_MINUTES) * BUCKET_MINUTES,
        second=0,
        microsecond=0,
    )
    return (adm2_name, intent, primary_item.strip().lower(), bucket.isoformat())


def find_duplicate(conn, key: tuple) -> int | None:
    """Looks up an existing ticket matching the bucket key, most recent
    first. The key isn't stored as literal columns on `tickets` -- adm2/
    intent are columns so the SQL narrows to the right 15-minute window
    cheaply, but items_json has to be parsed and compared in Python since
    "primary item" isn't a queryable column. Returns the ticket id, or
    None if nothing in this bucket matches."""
    adm2_name, intent, primary_item, bucket_iso = key
    bucket_start = datetime.fromisoformat(bucket_iso)
    bucket_end = bucket_start + timedelta(minutes=BUCKET_MINUTES)

    rows = conn.execute(
        """SELECT id, items_json FROM tickets
           WHERE adm2_name = ? AND intent = ?
             AND created_at >= ? AND created_at < ?
           ORDER BY created_at DESC""",
        (adm2_name, intent, bucket_start.isoformat(), bucket_end.isoformat()),
    ).fetchall()

    for row in rows:
        items = json.loads(row["items_json"] or "[]")
        if primary_item_from_items(items) == primary_item:
            return row["id"]
    return None
