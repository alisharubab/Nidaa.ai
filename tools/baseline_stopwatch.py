"""DATA-03: human baseline timing harness. Presents each message in
data/baseline_sample/manifest.json (or --manifest) one at a time, times how
long a human takes to read/listen and type the structured fields a
dispatcher would record, and writes the result to data/human_baseline.json
-- the number core/main.py's /api/metrics displays next to the system's
measured TTT (docs/PRD.md section 2.1).

This measures TIME only, not accuracy -- there's no answer key to score
against. Run it yourself, as if you were the dispatcher for real: read or
listen to each message, then type what you'd actually record.

Usage:
    python tools/baseline_stopwatch.py
    python tools/baseline_stopwatch.py --manifest data/gold_set/manifest.json
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def play_audio(path: str):
    full_path = REPO_ROOT / path
    try:
        if sys.platform == "win32":
            os.startfile(full_path)  # noqa: S606 -- local trusted file, opens default player
        elif sys.platform == "darwin":
            os.system(f'afplay "{full_path}" &')
        else:
            os.system(f'xdg-open "{full_path}" &')
    except Exception as e:
        print(f"  (couldn't auto-play -- open this file yourself: {full_path})  [{e}]")


def run_item(item: dict) -> dict:
    print(f"\n--- {item['id']} ({item['modality']}) ---")
    if item["modality"] == "text":
        print(f'  "{item["text"]}"')
    else:
        print("  (playing audio now -- listen, then answer below)")
        play_audio(item["audio_path"])

    start = time.perf_counter()
    district = input("  District: ").strip()
    intent = input("  Intent (resource_request/incident_report/infrastructure_damage/non_actionable): ").strip()
    urgency = input("  Urgency (critical/high/moderate/info): ").strip()
    items_needed = input("  Items/needs (freeform, e.g. 'food, water'): ").strip()
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    print(f"  -> {elapsed_ms} ms")
    return {
        "id": item["id"], "district": district, "intent": intent,
        "urgency": urgency, "items": items_needed, "elapsed_ms": elapsed_ms,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/baseline_sample/manifest.json")
    parser.add_argument("--out", default="data/human_baseline.json")
    args = parser.parse_args()

    manifest = json.loads((REPO_ROOT / args.manifest).read_text(encoding="utf-8"))
    print(f"Human baseline run -- {len(manifest)} messages. Answer as if you were the real dispatcher.")
    print("Ctrl+C at any point saves whatever's been timed so far.\n")

    results = []
    try:
        for item in manifest:
            results.append(run_item(item))
    except KeyboardInterrupt:
        print("\n\nStopped early -- saving what was recorded.")

    if not results:
        print("Nothing recorded, nothing saved.")
        return

    times = [r["elapsed_ms"] for r in results]
    times_sorted = sorted(times)
    n = len(times_sorted)
    median_ms = times_sorted[n // 2]
    p95_ms = times_sorted[int(n * 0.95)] if n > 1 else times_sorted[0]

    summary = {
        "median_ms": median_ms,
        "p95_ms": p95_ms,
        "n": n,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "per_item": results,
    }

    out_path = REPO_ROOT / args.out
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n=== {n} message(s) timed ===")
    print(f"median: {median_ms} ms ({median_ms/1000:.1f}s)")
    print(f"p95:    {p95_ms} ms ({p95_ms/1000:.1f}s)")
    print(f"Written to {out_path}")
    print("\nRemember: n is small (this is a first-pass sample, not the")
    print("final 25-message gold set) -- report it with that sample size attached.")


if __name__ == "__main__":
    main()
