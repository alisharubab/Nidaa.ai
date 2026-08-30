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


def _dominant_segment(segments: list) -> dict:
    """The longest-duration segment -- what "on the dominant segment" in
    TRD 4.3's no_speech_prob check means when a transcript has multiple
    segments. Not specified further in the TRD; duration is the least
    ambiguous read of "dominant"."""
    return max(segments, key=lambda s: s.get("end", 0) - s.get("start", 0))


def passes_confidence_gate(transcript_result: dict) -> bool:
    """Reject if ANY of: no_speech_prob > NO_SPEECH_MAX on the dominant
    segment, mean avg_logprob < AVG_LOGPROB_MIN, compression_ratio >
    COMPRESSION_MAX on any segment (the repetition-loop signature can
    appear in just one segment of an otherwise-normal transcript), or
    fewer than MIN_CONTENT_TOKENS words of actual content.

    "Tokens" is approximated as whitespace-split word count of the
    transcript text, not Whisper's raw token IDs -- those include
    timestamp/special tokens that aren't "content" in the sense TRD 4.3
    means (a transcript needs some actual words, not just structure).
    """
    text = transcript_result.get("text") or ""
    if len(text.split()) < MIN_CONTENT_TOKENS:
        return False

    segments = transcript_result.get("segments") or []
    if not segments:
        # Text without any segment metadata to gate on -- nothing to trust
        # a confidence decision against, so don't pass it by default.
        return False

    dominant = _dominant_segment(segments)
    if dominant.get("no_speech_prob", 0.0) > NO_SPEECH_MAX:
        return False

    mean_avg_logprob = sum(s.get("avg_logprob", 0.0) for s in segments) / len(segments)
    if mean_avg_logprob < AVG_LOGPROB_MIN:
        return False

    max_compression = max(s.get("compression_ratio", 0.0) for s in segments)
    if max_compression > COMPRESSION_MAX:
        return False

    return True


def transcribe_with_escalation(audio_path: str) -> dict:
    """Primary model, confidence gate, and — only on failure — exactly one
    retry against STT_MODEL_ESCALATION before giving up. Returns the last
    attempted transcript result with two extra keys the caller needs:
    "gate_passed" (bool) and "escalated" (bool, whether the escalation
    model was the one that produced this result).

    On gate_passed=False after escalation, the caller MUST set
    status=audio_unintelligible and skip pipeline.extract entirely — never
    pass a failed transcript to the LLM (docs/TRD.md section 4.3, hard
    rule 4 in ../../CLAUDE.md).
    """
    primary = transcribe(audio_path, model=STT_MODEL_PRIMARY)
    if passes_confidence_gate(primary):
        return {**primary, "gate_passed": True, "escalated": False}

    escalated = transcribe(audio_path, model=STT_MODEL_ESCALATION)
    return {**escalated, "gate_passed": passes_confidence_gate(escalated), "escalated": True}
