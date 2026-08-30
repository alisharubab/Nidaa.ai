# Stage 1: transcription + confidence gate + escalation. docs/TRD.md 4.3.

from groq import Groq

from config import GROQ_API_KEY, STT_MODEL_PRIMARY, STT_MODEL_ESCALATION

NO_SPEECH_MAX = 0.60
AVG_LOGPROB_MIN = -0.90
COMPRESSION_MAX = 2.40
MIN_CONTENT_TOKENS = 5

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def transcribe(audio_path: str, model: str = STT_MODEL_PRIMARY) -> dict:
    """Calls Groq's Whisper endpoint with response_format=verbose_json,
    temperature=0.0, language="ur" (hint, not hard constraint). Returns a
    plain dict (not the SDK's response object) so downstream code and the
    DB layer don't need to know about the Groq SDK's types.

    Confirmed working against real Urdu audio via CORE-05's smoke test.
    """
    client = _get_client()
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=f,
            model=model,
            language="ur",
            response_format="verbose_json",
            temperature=0.0,
        )
    return {
        "text": resp.text,
        "language": getattr(resp, "language", None),
        "segments": getattr(resp, "segments", None) or [],
        "model": model,
    }


def passes_confidence_gate(transcript_result: dict) -> bool:
    """Reject if ANY of: no_speech_prob > NO_SPEECH_MAX on the dominant
    segment, mean avg_logprob < AVG_LOGPROB_MIN, compression_ratio >
    COMPRESSION_MAX (Whisper repetition-loop signature), or fewer than
    MIN_CONTENT_TOKENS tokens of actual content.

    TODO(CORE-13): implement the gate logic against transcript_result.
    """
    raise NotImplementedError


def transcribe_with_escalation(audio_path: str) -> dict:
    """Primary model, confidence gate, and — only on failure — exactly one
    retry against STT_MODEL_ESCALATION before giving up.

    TODO(CORE-14): on a second gate failure, the caller must set
    status=audio_unintelligible and skip pipeline.extract entirely — never
    pass a failed transcript to the LLM (docs/TRD.md section 4.3).
    """
    raise NotImplementedError
