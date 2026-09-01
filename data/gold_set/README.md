# Gold Set (DATA-07 / DATA-10)

25 labelled evaluation messages per [TRD §8](../../docs/TRD.md#8-test-harness):
15 audio (5 clean / 5 moderate noise / 5 severe) and 10 text. Labels use the
exact intent/urgency vocabularies of `core/pipeline/extract.py`; every P-code
is a real adm2 code from `pak_gazetteer.csv` (nothing invented).

## Layout

```
data/gold_set/
  README.md            <- this file
  cases/
    a01/label.json     <- label + script to read aloud
    a01/audio.wav      <- YOU record this (a01..a10)
    ...
    t01/label.json     <- text cases carry the message inline ("text" field)
```

`tools/build_gold_set.py` (re)generates every `label.json` — the case specs
live in that script, so label edits happen there, then re-run it. Never edit
`label.json` by hand. Audio files are never touched by the generator.

## What you need to record (the only manual work)

**a01–a10 — 10 real human voice notes.** Read each case's `script` from its
`label.json` aloud on a phone, WhatsApp voice-note style: natural pace, Urdu,
2–3 sentences, quiet room for a01–a05. Copy each recording into its case
directory as `audio.wav` (m4a/ogg also work — the eval harness runs ffmpeg).
That gives 10 real recordings, above TRD's "at least 8 of 15" bar.

- a01–a05 are used as-is (clean tier).
- a06–a10 get noise mixed in for the moderate tier (below).

**a11–a15 — severe tier (TTS is fine).** Nobody can hear these anyway; the
gate must reject them. Build with edge-tts + heavy noise:

```powershell
pip install edge-tts
edge-tts --voice ur-PK-AsadNeural --text "Larkana mein paani aa gaya hai" --write-media a11_raw.mp3
ffmpeg -i a11_raw.mp3 -ar 16000 -ac 1 a11_clean.wav
ffmpeg -f lavfi -i "anoisesrc=color=pink:amplitude=1:duration=20" -ar 16000 -ac 1 a11_noise.wav
python tools/degrade_audio.py --clean a11_clean.wav --noise a11_noise.wav --snr-db -15 --out cases/a11/audio.wav
```

(-15 dB sits below the measured ~-8 to -10 dB give-up point, so both the
primary and escalation models must fail. See DATA-09 in PROGRESS.md.)

**Moderate tier noise for a06–a10:** same recipe but a *positive* SNR
(try `--snr-db 5` first). The point of the moderate tier is that extraction
still succeeds — if a case fails at +5 dB, try +8. Record which SNR you used
in the case dir as `build_notes.txt` so the ladder is reproducible. Using a
real rain/wind recording as the noise bed is better than synthetic pink
noise if you have one.

## Running the evaluation (DATA-10)

With core running (`uvicorn main:app` from `core/`) and the audio files in
place:

```powershell
python tools/gold_eval.py
```

It injects every case through the real pipeline (`POST /internal/ingest`),
waits for the verdict, and scores **exact district match + intent match**
per TRD §8 — unintelligible-tier cases score on the outcome (no ticket =
pass). Writes `eval_report.json` next to this README. Sample size is always
reported alongside the accuracy numbers.

`python tools/build_gold_set.py --check` tells you which audio files are
still missing.
