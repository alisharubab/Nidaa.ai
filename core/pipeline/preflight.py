# Stage 0: pre-flight audio check. docs/TRD.md section 4.2. Runs before any
# API quota is spent — rejects butt-dials and silent sends for free.

import json
import re
import subprocess

DURATION_MIN_S = 1.2
DURATION_MAX_S = 300.0
SILENCE_RMS_DB = -45.0  # mean_volume from `ffmpeg -af volumedetect`


def get_duration_s(audio_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", audio_path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def get_mean_volume_db(audio_path: str) -> float:
    # ffmpeg writes its log (including volumedetect's output) to stderr, not
    # stdout, regardless of exit code -- don't check=True here, `-f null -`
    # exits 0 on success but the data we want is in stderr either way.
    result = subprocess.run(
        ["ffmpeg", "-i", audio_path, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", result.stderr)
    if not match:
        raise RuntimeError(f"could not parse mean_volume from ffmpeg output for {audio_path}")
    return float(match.group(1))


def run_preflight(audio_path: str) -> dict:
    """Returns {"ok": True} or {"ok": False, "error_code": "AUDIO_TOO_SHORT"
    | "AUDIO_TOO_LONG" | "AUDIO_SILENT"}. Duration is checked before volume
    so a near-instant butt-dial never even triggers the (slower) volumedetect
    pass -- no API quota AND minimal local compute spent on obvious junk.
    """
    duration = get_duration_s(audio_path)
    if duration < DURATION_MIN_S:
        return {"ok": False, "error_code": "AUDIO_TOO_SHORT"}
    if duration > DURATION_MAX_S:
        return {"ok": False, "error_code": "AUDIO_TOO_LONG"}

    mean_volume = get_mean_volume_db(audio_path)
    if mean_volume < SILENCE_RMS_DB:
        return {"ok": False, "error_code": "AUDIO_SILENT"}

    return {"ok": True}
