"""DATA-10: run the gold set through the live pipeline and score it.

Requires core running (python -m uvicorn main:app --host 127.0.0.1
--port 8000 from core/). Cases come from data/gold_set/cases/*/label.json
(generated and validated by tools/build_gold_set.py).

Usage (from repo root):
    python tools/gold_eval.py                 # all 25 cases
    python tools/gold_eval.py t01 t10         # specific cases
    python tools/gold_eval.py --text-only     # the 10 text cases

Scoring per TRD section 8: exact district match + exact intent match
against the labels, with the sample size reported beside every number.
Cases in the unintelligible tier (a11-a15) score on the outcome instead:
pass iff the message ends audio_unintelligible and creates no ticket.

Non-wav audio is converted to 16 kHz mono wav with ffmpeg first (the
same normalisation the ingest daemon applies); cases with a missing
audio file are skipped and listed, never silently scored.

Writes data/gold_set/eval_report.json and prints a per-case table.

Re-running is safe: dedupe only flags near-duplicate tickets (15-minute
window), it never drops them, and every run gets a fresh wa_message_id.
"""

import json
import math
import sqlite3
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "data" / "gold_set" / "cases"
REPORT_PATH = ROOT / "data" / "gold_set" / "eval_report.json"
DB_PATH = ROOT / "core" / "nidaa.db"
CORE_URL = "http://127.0.0.1:8000"

CASE_TIMEOUT_S = 180  # per-case ceiling; live p95 is ~18 s, audio retries add more
TERMINAL_STATUSES = {"preflight_failed", "audio_unintelligible", "extracted", "failed"}


# --- core HTTP helpers (urllib: no extra dependency) ------------------------

def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        CORE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _core_up() -> bool:
    try:
        with urllib.request.urlopen(CORE_URL + "/api/metrics", timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


# --- audio prep (same normalisation ingest applies) -------------------------

def _prep_audio(case: dict) -> tuple[str, float] | tuple[None, None]:
    """Return (absolute wav path, duration_s) or (None, None) when the case
    has no audio file yet. Non-wav sources are converted once into
    storage/audio/ -- case directories are never written to."""
    src = next(iter(sorted((CASES_DIR / case["id"]).glob("audio.*"))), None)
    if src is None:
        return None, None
    if src.suffix.lower() == ".wav":
        wav = src
    else:
        wav = ROOT / "storage" / "audio" / f"gold_eval_{case['id']}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(wav)],
            check=True, capture_output=True,
        )
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(wav)],
        check=True, capture_output=True, text=True,
    )
    return str(wav.resolve()), float(probe.stdout.strip())


# --- pipeline observation (read-only DB polls) ------------------------------

def _query(sql: str, params: tuple) -> list[dict]:
    """Read-only query helper. Opens and closes the connection on every call
    so the long poll loops never hold handles on core's database."""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _await_terminal(message_id: int) -> dict:
    t0 = time.monotonic()
    while time.monotonic() - t0 < CASE_TIMEOUT_S:
        rows = _query("SELECT status, error_code FROM messages WHERE id = ?",
                      (message_id,))
        if rows and rows[0]["status"] in TERMINAL_STATUSES:
            return rows[0]
        time.sleep(1.0)
    return {"status": "timeout", "error_code": None}


_TICKETS_SQL = """SELECT t.adm2_name, t.intent, t.urgency, t.pcode,
                         t.created_at, m.t_received
                  FROM tickets t JOIN messages m ON m.id = t.message_id
                  WHERE t.message_id = ?"""


def _read_tickets(message_id: int, settle_s: float) -> list[dict]:
    """Tickets for a message. The worker may flip a message's status just
    before or after committing its tickets, so poll until the row count is
    stable (two consecutive equal non-zero reads) or the settle window ends."""
    rows, prev = [], []
    deadline = time.monotonic() + settle_s
    while time.monotonic() < deadline:
        rows = _query(_TICKETS_SQL, (message_id,))
        if rows and len(rows) == len(prev):
            break
        prev = rows
        time.sleep(0.5)
    return rows


# --- scoring -----------------------------------------------------------------

def _norm(values: list) -> list:
    """Sortable multiset normalisation (None-safe)."""
    return sorted(values, key=lambda v: (v is None, str(v)))


def _score(case: dict, status: str, tickets: list[dict]) -> dict:
    exp = case["expected"]
    result = {
        "district_ok": None, "intent_ok": None, "pass": False,
        "ttt_ms": [], "tickets": [],
    }
    for t in tickets:
        result["tickets"].append({
            "district": t["adm2_name"], "intent": t["intent"],
            "urgency": t["urgency"], "pcode": t["pcode"],
        })
        try:
            dt = (datetime.fromisoformat(t["created_at"])
                  - datetime.fromisoformat(t["t_received"]))
            result["ttt_ms"].append(round(dt.total_seconds() * 1000, 1))
        except (ValueError, TypeError):
            pass

    if exp["outcome"] == "audio_unintelligible":
        # outcome-scored: the gate must give up AND create no ticket
        result["pass"] = status == "audio_unintelligible" and not tickets
        return result

    exp_records = exp["records"]
    result["district_ok"] = _norm([r["district"] for r in exp_records]) == \
                            _norm([t["adm2_name"] for t in tickets])
    result["intent_ok"] = _norm([r["intent"] for r in exp_records]) == \
                          _norm([t["intent"] for t in tickets])
    result["pass"] = result["district_ok"] and result["intent_ok"] \
        and len(exp_records) == len(tickets)
    return result


# --- run ---------------------------------------------------------------------

def run_case(case: dict) -> dict:
    result = {
        "id": case["id"], "modality": case["modality"], "tier": case["noise_tier"],
        "expected_outcome": case["expected"]["outcome"], "status": None,
        "error_code": None, "skipped": False, "skip_reason": None,
    }
    payload = {
        "sender_hash": f"gold_{case['id']}",
        "phone_tail": "0000",
        "wa_message_id": f"gold-{case['id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    }
    if case["modality"] == "audio":
        audio_path, duration = _prep_audio(case)
        if audio_path is None:
            result["skipped"] = True
            result["skip_reason"] = "no audio file in case dir"
            return result
        payload.update({"modality": "audio", "audio_path": audio_path,
                        "audio_duration_s": duration})
    else:
        payload.update({"modality": "text", "text": case["text"]})

    _post("/internal/consent/check",
          {"sender_hash": payload["sender_hash"], "phone_tail": "0000"})
    ingest = _post("/internal/ingest", payload)
    message_id = ingest["message_id"]

    verdict = _await_terminal(message_id)
    result["status"], result["error_code"] = verdict["status"], verdict["error_code"]
    # no tickets can appear for an unintelligible message, so a long settle
    # window only burns time -- 0.5 s is enough to observe the empty set
    settle = 0.5 if case["expected"]["outcome"] == "audio_unintelligible" else 5.0
    tickets = _read_tickets(message_id, settle_s=settle)
    result.update(_score(case, verdict["status"], tickets))
    return result


def main() -> int:
    args = sys.argv[1:]
    text_only = "--text-only" in args
    wanted = {a for a in args if not a.startswith("--")}

    if not _core_up():
        print("core is not reachable at", CORE_URL)
        print("start it first:  cd core ; python -m uvicorn main:app --host 127.0.0.1 --port 8000")
        return 2

    cases = []
    for label in sorted(CASES_DIR.glob("*/label.json")):
        case = json.loads(label.read_text(encoding="utf-8"))
        if wanted and case["id"] not in wanted:
            continue
        if text_only and case["modality"] != "text":
            continue
        cases.append(case)
    if not cases:
        print("no cases selected -- check the case ids / flags")
        return 2

    results = []
    for case in cases:
        print(f"[{case['id']}] injecting ({case['modality']}, tier={case['noise_tier']}) ...",
              end=" ", flush=True)
        r = run_case(case)
        results.append(r)
        if r["skipped"]:
            print(f"SKIP ({r['skip_reason']})")
        else:
            mark = "PASS" if r["pass"] else "FAIL"
            detail = (f"{mark} status={r['status']}"
                      + (f" err={r['error_code']}" if r.get("error_code") else ""))
            if r["district_ok"] is not None:
                detail += f" district={'ok' if r['district_ok'] else 'MISS'}" \
                          f" intent={'ok' if r['intent_ok'] else 'MISS'}"
            print(detail)

    # --- aggregate (n reported beside every number, per TRD section 8) -----
    scored = [r for r in results if not r["skipped"]]
    extracted = [r for r in scored if r["expected_outcome"] == "extracted"]
    unintel = [r for r in scored if r["expected_outcome"] == "audio_unintelligible"]
    n_district_ok = sum(1 for r in extracted if r["district_ok"])
    n_intent_ok = sum(1 for r in extracted if r["intent_ok"])
    ttts = [t for r in extracted for t in r["ttt_ms"]]
    ttts_sorted = sorted(ttts)

    def pct(n, d):
        return round(n / d, 3) if d else None

    tiers = {}
    for tier in ("clean", "moderate", "severe", "text"):
        group = [r for r in scored if r["tier"] == tier]
        if group:
            tiers[tier] = {"n": len(group),
                           "passed": sum(1 for r in group if r["pass"])}

    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "n_total": len(results), "n_scored": len(scored),
        "n_skipped": len(results) - len(scored),
        "skipped": [r["id"] for r in results if r["skipped"]],
        "accuracy": {
            "overall": pct(sum(1 for r in scored if r["pass"]), len(scored)),
            "district": pct(n_district_ok, len(extracted)),
            "intent": pct(n_intent_ok, len(extracted)),
            "unintelligible_outcome": pct(sum(1 for r in unintel if r["pass"]),
                                          len(unintel)),
            "n": len(scored), "n_extracted": len(extracted),
            "n_unintelligible": len(unintel),
        },
        "tiers": tiers,
        "ttt_ms": {
            "median": round(statistics.median(ttts), 1) if ttts else None,
            "p95": ttts_sorted[min(len(ttts_sorted) - 1,
                                   max(0, math.ceil(0.95 * len(ttts_sorted)) - 1))]
                   if ttts_sorted else None,
            "n": len(ttts),
        },
        "cases": results,
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"scored {len(scored)}/{len(results)} cases"
          + (f" (skipped: {', '.join(report['skipped'])})" if report["skipped"] else ""))
    a = report["accuracy"]
    print(f"overall accuracy      {a['overall']} (n={a['n']})")
    print(f"district accuracy     {a['district']} (n={a['n_extracted']} extracted cases)")
    print(f"intent accuracy       {a['intent']} (n={a['n_extracted']})")
    if unintel:
        print(f"unintelligible tier   {a['unintelligible_outcome']} (n={a['n_unintelligible']})")
    t = report["ttt_ms"]
    print(f"TTT                   median {t['median']} ms, p95 {t['p95']} ms (n={t['n']} tickets)")
    print(f"report written to {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
