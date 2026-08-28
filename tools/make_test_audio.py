"""Generates synthetic Urdu voice notes with edge-tts (free, no API key).
See docs/TRD.md section 8.

Voices: ur-PK-AsadNeural, ur-PK-UzmaNeural.

Usage (once implemented):
    python tools/make_test_audio.py --text "..." --voice ur-PK-AsadNeural --out out.wav

TODO(DATA-05 prerequisite): install `edge-tts`, synthesize the gold-set
script lines, and remember TTS audio is unrealistically clean — at least
8 of the 15 gold-set audio samples must be real human recordings instead
(docs/TRD.md section 8, "Important" note).
"""

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--voice", default="ur-PK-AsadNeural")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    raise NotImplementedError("wire up edge-tts here")


if __name__ == "__main__":
    main()
