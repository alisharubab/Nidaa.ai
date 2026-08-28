"""Mixes rain/wind noise beds over clean samples at defined SNR steps using
ffmpeg amix. Produces the acoustic degradation ladder used to find the SNR
point where the confidence gate correctly gives up. See docs/TRD.md section 8
and section 4.3 (the confidence gate this test is validating against).

Usage (once implemented):
    python tools/degrade_audio.py --clean clean.wav --noise rain.wav --snr-db 5 --out degraded.wav

TODO(DATA-05): implement the ffmpeg amix invocation across a range of SNR
steps, and DATA-09: run the full ladder against pipeline.stt to record the
give-up point.
"""

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", required=True)
    parser.add_argument("--noise", required=True)
    parser.add_argument("--snr-db", type=float, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    raise NotImplementedError("wire up ffmpeg amix here")


if __name__ == "__main__":
    main()
