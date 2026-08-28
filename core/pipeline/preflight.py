# Stage 0: pre-flight audio check. docs/TRD.md section 4.2. Runs before any
# API quota is spent — rejects butt-dials and silent sends for free.

DURATION_MIN_S = 1.2
DURATION_MAX_S = 300.0
SILENCE_RMS_DB = -45.0  # mean_volume from `ffmpeg -af volumedetect`


def run_preflight(audio_path: str) -> dict:
    """Returns {"ok": True} or {"ok": False, "error_code": "AUDIO_TOO_SHORT"
    | "AUDIO_TOO_LONG" | "AUDIO_SILENT"}.

    TODO(CORE-06):
      1. `ffprobe -v error -show_entries format=duration -of json <path>`
         to get duration; compare against DURATION_MIN_S / DURATION_MAX_S.
      2. `ffmpeg -i <path> -af volumedetect -f null -` to get mean_volume;
         compare against SILENCE_RMS_DB.
    """
    raise NotImplementedError
