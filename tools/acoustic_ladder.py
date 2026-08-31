"""DATA-09: runs a clean sample through an SNR ladder (via degrade_audio.py)
and records where pipeline.stt's confidence gate -- with escalation --
actually gives up. See docs/TRD.md section 8.

This is the reusable ladder-runner. The FORMAL DATA-09 result (docs/TRD.md:
"the 5 clean samples are re-mixed with rain and wind at increasing gain")
needs the 5 real clean gold-set samples from DATA-07, which don't exist
yet -- this run uses ad-hoc synthetic samples to characterize the gate now
rather than block on the gold set. Re-run this against the real 5 once
DATA-07 lands; don't treat this run's exact numbers as the final reported
threshold.

Usage:
    python tools/acoustic_ladder.py --clean clean.wav --noise noise.wav
"""

import argparse
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from pipeline.stt import gate_failure_reason, transcribe  # noqa: E402
from degrade_audio import degrade  # noqa: E402

DEFAULT_LADDER = [5, 0, -5, -10, -15, -20, -25, -30]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", required=True)
    parser.add_argument("--noise", required=True)
    parser.add_argument("--ladder", type=float, nargs="+", default=DEFAULT_LADDER)
    args = parser.parse_args()

    print(f"{'SNR (dB)':>10} | {'gate':>6} | {'reason':<20} | transcript")
    print("-" * 90)

    give_up_snr = None
    with tempfile.TemporaryDirectory() as tmp:
        for snr in args.ladder:
            out_path = str(Path(tmp) / f"degraded_{snr}.wav")
            degrade(args.clean, args.noise, snr, out_path)
            result = transcribe(out_path)
            reason = gate_failure_reason(result)
            gate = "PASS" if reason is None else "FAIL"
            preview = (result["text"] or "").strip()[:40]
            print(f"{snr:>10.0f} | {gate:>6} | {reason or '-':<20} | {preview}")
            if reason is not None and give_up_snr is None:
                give_up_snr = snr

    print()
    if give_up_snr is not None:
        print(f"Confidence gate first failed at {give_up_snr} dB SNR (primary model, no escalation in this sweep).")
    else:
        print("Gate never failed across this ladder -- extend it to lower (more negative) SNR values.")


if __name__ == "__main__":
    main()
