# Stage 5: near-duplicate flagging. docs/TRD.md section 4.7.
# No vector DB in the MVP. Key on (adm2_name, intent, normalised_primary_item,
# 15-minute bucket). Duplicates are flagged and counted, never deleted.

from datetime import datetime

BUCKET_MINUTES = 15


def bucket_key(adm2_name: str, intent: str, primary_item: str, created_at: datetime) -> tuple:
    bucket = created_at.replace(
        minute=(created_at.minute // BUCKET_MINUTES) * BUCKET_MINUTES,
        second=0,
        microsecond=0,
    )
    return (adm2_name, intent, primary_item.strip().lower(), bucket.isoformat())


def find_duplicate(conn, key: tuple) -> int | None:
    """Looks up an existing ticket with a matching bucket key. Returns its
    ticket id, or None. TODO(CORE-20): implement the lookup query — likely
    easiest as a derived column or an in-memory index refreshed per bucket,
    since the key isn't stored as literal columns on `tickets`."""
    raise NotImplementedError
