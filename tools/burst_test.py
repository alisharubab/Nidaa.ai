"""Fires 50 concurrent POSTs to /internal/ingest. See docs/TRD.md section 8
and the Definition of Done item 7 (docs/TRD.md section 12).

Pass criteria: zero 5xx responses, zero SQLite "database is locked" errors,
zero unhandled 429s, and a final row count of exactly 50 in `messages`.

Usage (once implemented):
    python tools/burst_test.py --core-url http://127.0.0.1:8000 --count 50

TODO(DATA-08): implement with asyncio + httpx (or aiohttp), gather results,
assert the pass criteria above, and print a pass/fail summary.
"""

import argparse
import asyncio


async def fire_burst(core_url: str, count: int):
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-url", default="http://127.0.0.1:8000")
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(fire_burst(args.core_url, args.count))


if __name__ == "__main__":
    main()
