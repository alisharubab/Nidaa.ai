# Stage 2: LLM structured extraction. docs/TRD.md section 4.4 and section 5
# (the full system prompt lives in prompts/system_extract.txt).

import json
from pathlib import Path

from config import LLM_MODEL_PRIMARY, LLM_MODEL_FALLBACK

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_system_prompt() -> str:
    """Loads prompts/system_extract.txt and injects prompts/glossary.json
    so a non-engineer can extend the glossary without touching Python."""
    template = (PROMPTS_DIR / "system_extract.txt").read_text(encoding="utf-8")
    glossary = json.loads((PROMPTS_DIR / "glossary.json").read_text(encoding="utf-8"))
    # TODO(CORE-17): decide the exact injection point/format for glossary
    # entries into `template` (the .txt already ships a glossary section —
    # keep the two in sync or fold one into the other).
    return template


class ExtractionValidationError(Exception):
    pass


def extract(transcript: str, model: str = LLM_MODEL_PRIMARY) -> dict:
    """Calls the Groq chat completions endpoint with response_format=
    {"type": "json_object"}, temperature=0.1, max_tokens=1200, then
    validates the result against a Pydantic model matching the schema in
    docs/TRD.md section 4.4.

    IMPORTANT (confirmed via smoke_test_groq.py, CORE-05): LLM_MODEL_FALLBACK
    (qwen/qwen3.6-27b) is a Groq "reasoning" model. Calling it with
    response_format=json_object and NO reasoning_format set fails outright
    (400 json_validate_failed) -- it emits a <think>...</think> block before
    the answer, which breaks JSON parsing. When model == LLM_MODEL_FALLBACK,
    the call MUST also pass reasoning_format="hidden" and
    reasoning_effort="none" (no benefit from chain-of-thought on a
    structured-extraction task). LLM_MODEL_PRIMARY (GPT-OSS) does NOT
    support or need reasoning_format -- it already returns reasoning in a
    separate field by default, so passing these params to the primary
    model call would be wrong, not just redundant.

    TODO(CORE-08): implement the call + Pydantic validation. Raise
    ExtractionValidationError on a parse/schema failure so the caller can
    retry once against LLM_MODEL_FALLBACK (docs/TRD.md: never fall back to
    a partially-parsed guess — two failures means status=failed,
    error_code=EXTRACTION_INVALID).
    """
    raise NotImplementedError


def extract_with_fallback(transcript: str) -> dict:
    """Primary model, then exactly one retry on LLM_MODEL_FALLBACK if the
    first attempt raises ExtractionValidationError. TODO(CORE-16). See the
    reasoning_format note on extract() above -- the fallback call needs
    different kwargs than the primary call, not just a different model ID.
    """
    raise NotImplementedError
