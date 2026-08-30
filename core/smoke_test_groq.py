"""CORE-05: Groq smoke test. Confirms GROQ_API_KEY works and all four
model IDs (docs/TRD.md section 1) are actually reachable on your account's
free tier, BEFORE the real pipeline is built around them.

This is a connectivity/auth/schema check, not an accuracy benchmark --
that's DATA-07/DATA-09/DATA-10's job once the gold set exists.

Usage:
    python smoke_test_groq.py path/to/test.wav
"""

import json
import sys

# Windows' console defaults to cp1252, which can't print Urdu script --
# without this, a successful transcript containing Urdu text crashes the
# print statement AFTER the API call already succeeded, which looks like
# an API failure when it isn't one.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from groq import Groq

from config import (
    GROQ_API_KEY, STT_MODEL_PRIMARY, STT_MODEL_ESCALATION,
    LLM_MODEL_PRIMARY, LLM_MODEL_FALLBACK,
)

SYSTEM_PROMPT_PATH = "prompts/system_extract.txt"


def check(label: str, fn):
    print(f"\n=== {label} ===")
    try:
        fn()
        print(f"OK -- {label}")
        return True
    except Exception as e:
        print(f"FAILED -- {label}: {type(e).__name__}: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python smoke_test_groq.py path/to/test.wav")
        sys.exit(1)
    audio_path = sys.argv[1]

    if not GROQ_API_KEY:
        print("GROQ_API_KEY is empty -- check .env at the repo root.")
        sys.exit(1)

    client = Groq(api_key=GROQ_API_KEY)
    results = []

    def stt_primary():
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                file=f, model=STT_MODEL_PRIMARY, language="ur",
                response_format="verbose_json", temperature=0.0,
            )
        print("  transcript:", resp.text)
        segs = getattr(resp, "segments", None) or []
        if segs:
            print("  segments:", len(segs))
            print("  avg_logprob (seg 0):", segs[0].get("avg_logprob"))
            print("  no_speech_prob (seg 0):", segs[0].get("no_speech_prob"))
            print("  compression_ratio (seg 0):", segs[0].get("compression_ratio"))

    def stt_escalation():
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                file=f, model=STT_MODEL_ESCALATION, language="ur",
                response_format="verbose_json", temperature=0.0,
            )
        print("  transcript:", resp.text)

    def llm_primary():
        system_prompt = open(SYSTEM_PROMPT_PATH, encoding="utf-8").read()
        resp = client.chat.completions.create(
            model=LLM_MODEL_PRIMARY,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Dadu mein bees gharon ko khana aur saaf pani chahiye, halat ghair ha."},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1200,
        )
        content = resp.choices[0].message.content
        parsed = json.loads(content)  # will raise if the model didn't return valid JSON
        print("  raw response:", json.dumps(parsed, indent=2, ensure_ascii=False))
        assert "records" in parsed, "response missing top-level 'records' key"
        assert parsed["records"][0]["urgency"] == "critical", "expected 'halat ghair ha' to force critical urgency"
        assert "latitude" not in json.dumps(parsed).lower().replace("calibrate", ""), "model must never emit coordinates"

    def llm_fallback():
        # LLM_MODEL_FALLBACK (qwen/qwen3.6-27b) is a Groq "reasoning" model.
        # Without reasoning_format="hidden" (or "parsed"), it emits a
        # <think>...</think> block before the answer, which breaks strict
        # JSON mode entirely (400 json_validate_failed). reasoning_effort=
        # "none" additionally skips the reasoning step outright, which is
        # what we want for a structured-extraction task with no benefit
        # from chain-of-thought. GPT-OSS models (the primary) don't need
        # this -- they return reasoning in a separate field by default.
        system_prompt = open(SYSTEM_PROMPT_PATH, encoding="utf-8").read()
        resp = client.chat.completions.create(
            model=LLM_MODEL_FALLBACK,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Dadu mein bees gharon ko khana aur saaf pani chahiye, halat ghair ha."},
            ],
            response_format={"type": "json_object"},
            reasoning_format="hidden",
            reasoning_effort="none",
            temperature=0.1,
            max_tokens=1200,
        )
        content = resp.choices[0].message.content
        parsed = json.loads(content)
        print("  raw response:", json.dumps(parsed, indent=2, ensure_ascii=False))
        assert "records" in parsed, "response missing top-level 'records' key"

    results.append(check(f"STT primary ({STT_MODEL_PRIMARY})", stt_primary))
    results.append(check(f"STT escalation ({STT_MODEL_ESCALATION})", stt_escalation))
    results.append(check(f"LLM primary ({LLM_MODEL_PRIMARY})", llm_primary))
    results.append(check(f"LLM fallback ({LLM_MODEL_FALLBACK})", llm_fallback))

    print(f"\n{sum(results)}/{len(results)} checks passed.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
