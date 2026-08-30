"""Mixes a noise bed over a clean sample at a target SNR using ffmpeg amix.
Produces the acoustic degradation ladder used to find the SNR point where
the confidence gate (pipeline/stt.py) correctly gives up. See docs/TRD.md
section 8 and section 4.3.

Usage:
    python tools/degrade_audio.py --clean clean.wav --noise rain.wav --snr-db 5 --out degraded.wav

If you don't have a real rain/wind recording handy, synthesize a stand-in
noise bed first (no download, no licensing question -- ffmpeg's built-in
noise generator):
    ffmpeg -f lavfi -i "anoisesrc=color=pink:amplitude=1:duration=10" -ar 16000 -ac 1 noise.wav

Real environmental recordings (actual rain/wind) will be more realistic
for the final DATA-09 degradation-ladder run than synthetic pink noise --
this is a reasonable stand-in for development/testing, not a replacement
for the real thing before that run.
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from pipeline.preflight import get_duration_s, get_mean_volume_db  # noqa: E402


def degrade(clean_path: str, noise_path: str, snr_db: float, out_path: str) -> None:
    """Mixes noise over the clean signal so the noise sits `snr_db` decibels
    below the clean signal's mean volume -- a lower snr_db means louder,
    more disruptive noise relative to the speech."""
    clean_db = get_mean_volume_db(clean_path)
    noise_db = get_mean_volume_db(noise_path)
    clean_duration = get_duration_s(clean_path)

    target_noise_db = clean_db - snr_db
    gain_adjust = target_noise_db - noise_db

    filter_complex = (
        f"[1:a]volume={gain_adjust:.2f}dB,atrim=0:{clean_duration:.3f}[noise_adj];"
        f"[0:a][noise_adj]amix=inputs=2:duration=first:dropout_transition=0[out]"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", clean_path,
            "-stream_loop", "-1", "-i", noise_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            out_path,
        ],
        capture_output=True, text=True, check=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", required=True)
    parser.add_argument("--noise", required=True)
    parser.add_argument("--snr-db", type=float, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    degrade(args.clean, args.noise, args.snr_db, args.out)
    print(f"Wrote {args.out} at {args.snr_db} dB SNR")


if __name__ == "__main__":
    main()
