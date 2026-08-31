"""DATA-08: fires N concurrent messages at a running core/ instance and
verifies the queue/DB layer holds up under load. See docs/TRD.md section 8
and the Definition of Done item 7 (docs/TRD.md section 12).

Pass criteria, straight from docs/TRD.md section 8: zero crashes, zero
SQLite "database is locked" errors, zero UNHANDLED rate-limit failures,
and a final row count of exactly N. Note "unhandled" -- a message that
exhausts its 3 retry attempts (docs/TRD.md 4.1) and lands on
status=failed/error_code=RATE_LIMITED is a HANDLED 429: retried with
backoff, then failed gracefully with a specific, correct reason, not
crashed/lost/corrupted. Under real burst load some RATE_LIMITED outcomes
are expected and correct, not a test failure -- this script reports the
status breakdown so you can see how many, not just pass/fail on whether
any exist. What WOULD fail this test: fewer than N total message rows,
any message stuck at "received" after the wait (dropped, not handled), or
any 5xx / DB-lock error.

Usage:
    python tools/burst_test.py --core-url http://127.0.0.1:8000 --count 50
"""

import argparse
import asyncio
import time
from collections import Counter

import httpx
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
import db  # noqa: E402


async def fire_one(client: httpx.AsyncClient, core_url: str, i: int) -> dict:
    sender_hash = f"sha256:burst-{i}"
    consent_resp = await client.post(
        f"{core_url}/internal/consent/check",
        json={"sender_hash": sender_hash, "phone_tail": f"{i:03d}"},
    )
    ingest_resp = await client.post(
        f"{core_url}/internal/ingest",
        json={
            "wa_message_id": f"burst-{i}",
            "sender_hash": sender_hash,
            "phone_tail": f"{i:03d}",
            "modality": "text",
            "text": f"Burst test message {i}: Dadu mein khana chahiye.",
        },
    )
    return {
        "i": i,
        "consent_status": consent_resp.status_code,
        "ingest_status": ingest_resp.status_code,
        "message_id": ingest_resp.json().get("message_id") if ingest_resp.status_code == 200 else None,
    }


async def run(core_url: str, count: int, max_wait_seconds: float):
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Firing {count} concurrent messages at {core_url} ...")
        start = time.monotonic()
        results = await asyncio.gather(*(fire_one(client, core_url, i) for i in range(count)))
        fired_elapsed = time.monotonic() - start

        server_errors = [r for r in results if r["consent_status"] >= 500 or r["ingest_status"] >= 500]
        message_ids = [r["message_id"] for r in results if r["message_id"] is not None]

        # Poll queue_depth instead of guessing a fixed sleep -- with a
        # shared 25 RPM LLM bucket (docs/TRD.md 4.1) and real API latency
        # variance, a fixed wait either finishes early (wasted time) or
        # too late (looks like a failure when it's just still working).
        print(f"Fired {count} messages in {fired_elapsed:.2f}s. Polling until the queue drains (max {max_wait_seconds:.0f}s) ...")
        drain_start = time.monotonic()
        while time.monotonic() - drain_start < max_wait_seconds:
            metrics_resp = await client.get(f"{core_url}/api/metrics")
            metrics = metrics_resp.json()
            if metrics["queue_depth"] == 0:
                break
            await asyncio.sleep(3)
        drain_elapsed = time.monotonic() - drain_start
        print(f"Drained in {drain_elapsed:.0f}s (queue_depth={metrics['queue_depth']})")

    # Reads nidaa.db directly for the final status breakdown -- there's no
    # HTTP endpoint that lists messages by status, and adding one just for
    # this script would be scope creep. This is a deliberate, scoped
    # exception: burst_test.py is a local dev tool run on the same machine
    # as core/, not a black-box client of a remote deployment (unlike
    # ingest/, core/, dashboard/, which the architecture forbids
    # cross-importing between -- see ../CLAUDE.md hard rule 2, which names
    # those three runtimes specifically, not tools/).
    core_db_path = str(Path(__file__).parent.parent / "core" / "nidaa.db")
    with db.get_connection(core_db_path) as conn:
        rows = conn.execute("SELECT status, error_code, COUNT(*) c FROM messages GROUP BY status, error_code").fetchall()
    status_counts = Counter()
    for row in rows:
        label = row["status"] if row["error_code"] is None else f"{row['status']} ({row['error_code']})"
        status_counts[label] = row["c"]
    total_rows = sum(status_counts.values())

    print()
    print("=== Results ===")
    print(f"5xx responses:            {len(server_errors)} (want 0)")
    print(f"message_ids returned:     {len(message_ids)} / {count} (want {count})")
    print(f"final queue_depth:        {metrics['queue_depth']} (want 0 -- everything drained)")
    print(f"total message rows:       {total_rows} (want exactly {count})")
    print("status breakdown:")
    for label, c in status_counts.most_common():
        print(f"  {label}: {c}")
    stuck = status_counts.get("received", 0)
    if stuck:
        print(f"  ^ {stuck} message(s) still 'received' after the wait -- dropped, not handled")

    # Pass criteria per docs/TRD.md section 8: zero 5xx, exactly `count`
    # total rows, nothing stuck at "received" (that would mean dropped,
    # not handled). RATE_LIMITED outcomes are NOT a failure here -- they
    # ARE the handled case (retried per docs/TRD.md 4.1, then failed with
    # a specific reason instead of crashing or losing the message).
    ok = (
        len(server_errors) == 0
        and len(message_ids) == count
        and metrics["queue_depth"] == 0
        and total_rows == count
        and stuck == 0
    )
    print()
    print("PASS" if ok else "FAIL -- see above")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-url", default="http://127.0.0.1:8000")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--wait", type=float, default=300.0, help="max seconds to poll for the queue to drain before giving up")
    args = parser.parse_args()
    ok = asyncio.run(run(args.core_url, args.count, args.wait))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
