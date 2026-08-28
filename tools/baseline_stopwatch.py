"""CLI that plays a gold-set message, waits for a human to type the
structured fields, and records elapsed time. Produces human_baseline_ms,
the comparison number for the North Star Metric (docs/PRD.md section 2.1).

Usage (once implemented):
    python tools/baseline_stopwatch.py --gold-set data/gold_set

TODO(DATA-03): for each message in the gold set, play the audio (or print
the text), start a timer, prompt for district/intent/urgency/items input,
stop the timer on submission, and write results (with median/p95) to a
report file. Do this run EARLY (Day 1) -- it anchors the whole demo.
"""

import argparse
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-set", default="data/gold_set")
    args = parser.parse_args()
    raise NotImplementedError("wire up the stopwatch loop here")


if __name__ == "__main__":
    main()
