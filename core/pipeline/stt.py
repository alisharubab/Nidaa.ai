# Stage 1: transcription + confidence gate + escalation. docs/TRD.md 4.3.

from groq import Groq
from rapidfuzz import fuzz

from config import GROQ_API_KEY, STT_MODEL_PRIMARY, STT_MODEL_ESCALATION

NO_SPEECH_MAX = 0.60
AVG_LOGPROB_MIN = -0.90
COMPRESSION_MAX = 2.40
MIN_CONTENT_TOKENS = 5

# docs/TRD.md 4.3 addendum: a fluent Whisper hallucination can score
# confidently on every metric above (low no_speech_prob, high avg_logprob,
# normal compression) because none of them measure whether the text is
# actually GROUNDED in the audio -- only whether the model sounds sure of
# itself. See transcripts_agree() below.
MODEL_AGREEMENT_MIN_RATIO = 55

# Whisper's `prompt` biases its decoder toward these tokens without hard-
# constraining the transcript to them (unlike `language`). Without this,
# language="ur" pushes the decoder to force every acoustic frame into Urdu
# vocabulary, so common English loanwords a Pakistani speaker code-switches
# in ("boats", "rations", "medical kit") get mapped to acoustically-similar
# but wrong Urdu words instead (e.g. "boats" -> "بہت"/bohat = "a lot") --
# the LLM downstream then has nothing to extract. Bilingual on purpose: an
# all-Urdu prompt suppresses the English words this is meant to protect,
# an all-English one risks nudging transcription toward English. Kept
# under ~50 words / ~300 characters, comfortably inside Whisper's prompt
# token budget (~224 tokens) -- a prompt that gets silently truncated loses
# exactly the biasing tokens it was added for.
CRISIS_PROMPT = (
    "سیلاب، امدادی کارروائی، ریسکیو، راشن، کشتیاں، خیمے، دوائیاں، پینے کا صاف پانی، "
    "بچے، حاملہ خواتین، بزرگ، پھنسے ہوئے، مکانات گر گئے، بند ٹوٹ گیا، "
    "boats, rescue boats, rations, dry ration, food packs, tents, tarpaulin, "
    "medical camp, medicines, ORS, snake bite, pregnant women, casualties, "
    "trapped, flood relief."
)

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def transcribe(audio_path: str, model: str = STT_MODEL_PRIMARY, temperature: float = 0.0) -> dict:
    """Calls Groq's Whisper endpoint with response_format=verbose_json,
    language="ur" (hint, not hard constraint), and CRISIS_PROMPT to bias
    against code-switched English loanwords being misheard as Urdu.
    Returns a plain dict (not the SDK's response object) so downstream code
    and the DB layer don't need to know about the Groq SDK's types.

    `temperature` defaults to 0.0 (deterministic) but main.py's escalation
    call raises it for the retry -- temperature=0.0 is exactly what can lock
    Whisper into a repetition loop on noisy audio (the same failure
    gate_failure_reason() detects via COMPRESSION_MAX); a little sampling
    randomness on the second attempt gives it a chance to escape one instead
    of deterministically reproducing the same loop.

    Confirmed working against real Urdu audio via CORE-05's smoke test.
    """
    client = _get_client()
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=f,
            model=model,
            language="ur",
            prompt=CRISIS_PROMPT,
            response_format="verbose_json",
            temperature=temperature,
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


def gate_failure_reason(transcript_result: dict) -> str | None:
    """None if the transcript passes the confidence gate. Otherwise the
    specific docs/TRD.md section 9 error_code: "STT_REPETITION_LOOP" if
    the compression-ratio signature is present (checked first -- it's the
    most specific, attributable failure mode; TRD 4.3: "must be caught,
    because it produces long, fluent, entirely fake transcripts"),
    otherwise the general "STT_LOW_CONFIDENCE" for any of the other three
    conditions: no_speech_prob > NO_SPEECH_MAX on the dominant segment,
    mean avg_logprob < AVG_LOGPROB_MIN, or fewer than MIN_CONTENT_TOKENS
    words of actual content.

    "Tokens" is approximated as whitespace-split word count of the
    transcript text, not Whisper's raw token IDs -- those include
    timestamp/special tokens that aren't "content" in the sense TRD 4.3
    means (a transcript needs some actual words, not just structure).

    CORE-24 hardening note: this used to be a single passes_confidence_gate
    -> bool function. Split so the caller (main.py) can record which
    specific error_code applies, per TRD section 9's error taxonomy --
    previously everything that failed the gate was recorded as the same
    generic STT_LOW_CONFIDENCE, losing the repetition-loop signal.
    """
    segments = transcript_result.get("segments") or []
    if segments:
        max_compression = max(s.get("compression_ratio", 0.0) for s in segments)
        if max_compression > COMPRESSION_MAX:
            return "STT_REPETITION_LOOP"

    text = transcript_result.get("text") or ""
    if len(text.split()) < MIN_CONTENT_TOKENS:
        return "STT_LOW_CONFIDENCE"

    if not segments:
        # Text without any segment metadata to gate on -- nothing to trust
        # a confidence decision against, so don't pass it by default.
        return "STT_LOW_CONFIDENCE"

    dominant = _dominant_segment(segments)
    if dominant.get("no_speech_prob", 0.0) > NO_SPEECH_MAX:
        return "STT_LOW_CONFIDENCE"

    mean_avg_logprob = sum(s.get("avg_logprob", 0.0) for s in segments) / len(segments)
    if mean_avg_logprob < AVG_LOGPROB_MIN:
        return "STT_LOW_CONFIDENCE"

    return None


def transcripts_agree(text_a: str, text_b: str) -> bool:
    """Self-consistency check (docs/TRD.md 4.3 addendum): two independent
    samples of the SAME audio, at the same model/temperature, should land
    on roughly the same content if there's real speech behind them. A
    hallucination has no acoustic signal anchoring it, so a resample tends
    to invent different fabricated text each time -- unlike a genuinely
    noisy-but-real transcript, which mostly agrees with itself even if a
    word or two differs.

    token_set_ratio (not plain ratio) is deliberately order/subset-tolerant
    -- two correct transcriptions of the same speech can differ slightly in
    filler words or segmentation without that counting as disagreement.
    MODEL_AGREEMENT_MIN_RATIO=55 is a first real threshold, not a value
    pulled from the spec (no TRD-given cutoff exists for this); worth
    revisiting once more real hallucination cases exist to tune against."""
    return fuzz.token_set_ratio(text_a or "", text_b or "") >= MODEL_AGREEMENT_MIN_RATIO


def passes_confidence_gate(transcript_result: dict) -> bool:
    """Convenience boolean wrapper -- see gate_failure_reason() for the
    docs/TRD.md 4.3 conditions and their section 9 error_code."""
    return gate_failure_reason(transcript_result) is None


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
