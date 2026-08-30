# Stage 2: LLM structured extraction. docs/TRD.md section 4.4 and section 5
# (the full system prompt lives in prompts/system_extract.txt).

import json
from pathlib import Path
from typing import Literal, Optional

from groq import Groq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from config import GROQ_API_KEY, LLM_MODEL_PRIMARY, LLM_MODEL_FALLBACK

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


# --- Output schema (docs/TRD.md section 4.4) --------------------------------

class ExtractedItem(BaseModel):
    item: str
    qty: Optional[int] = None
    unit: Optional[str] = None


class ExtractionRecord(BaseModel):
    # extra="forbid": if the model ever emits an unexpected key -- most
    # importantly "latitude"/"longitude"/"pcode", which the prompt
    # explicitly forbids (hard rule #3, docs/TRD.md section 4.4 rule 2) --
    # validation fails loudly instead of silently dropping the extra field.
    # A model that tries to invent a coordinate should trigger the
    # fallback-retry / EXTRACTION_INVALID path, not have the violation
    # quietly discarded by Pydantic's default "ignore extra fields".
    model_config = ConfigDict(extra="forbid")

    intent: Literal["resource_request", "incident_report", "infrastructure_damage", "non_actionable"]
    urgency: Literal["critical", "high", "moderate", "info"]
    location_raw: Optional[str] = None
    district_guess: Optional[str] = None
    province_guess: Optional[str] = None
    items: list[ExtractedItem] = Field(default_factory=list)
    people_affected: Optional[int] = None
    casualties: Optional[int] = None
    missing_fields: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    reasoning_note: str = ""


class ExtractionResponse(BaseModel):
    records: list[ExtractionRecord]


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
    validates the result against ExtractionResponse (docs/TRD.md 4.4).
    Raises ExtractionValidationError on a JSON-parse or schema failure --
    the caller decides whether/how to retry. Never falls back to a
    partially-parsed guess (docs/TRD.md 4.4).

    LLM_MODEL_FALLBACK (qwen/qwen3.6-27b) is a Groq "reasoning" model --
    confirmed via CORE-05's smoke test that it needs reasoning_format=
    "hidden" and reasoning_effort="none" to produce valid JSON at all (see
    the TRD 4.4 addendum). LLM_MODEL_PRIMARY (GPT-OSS) doesn't support or
    need those kwargs, so they're only added when calling the fallback.
    """
    client = _get_client()
    system_prompt = load_system_prompt()

    kwargs = {}
    if model == LLM_MODEL_FALLBACK:
        kwargs["reasoning_format"] = "hidden"
        kwargs["reasoning_effort"] = "none"

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1200,
        **kwargs,
    )
    content = resp.choices[0].message.content

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ExtractionValidationError(f"model did not return valid JSON: {e}") from e

    try:
        validated = ExtractionResponse.model_validate(parsed)
    except ValidationError as e:
        raise ExtractionValidationError(f"schema validation failed: {e}") from e

    return validated.model_dump()


def extract_with_fallback(transcript: str) -> dict:
    """Primary model, then exactly one retry on LLM_MODEL_FALLBACK if the
    first attempt raises ExtractionValidationError. A second failure
    propagates ExtractionValidationError to the caller, which must set
    status=failed, error_code=EXTRACTION_INVALID (docs/TRD.md 4.4) --
    this function itself never swallows a double failure.
    """
    try:
        return extract(transcript, model=LLM_MODEL_PRIMARY)
    except ExtractionValidationError:
        return extract(transcript, model=LLM_MODEL_FALLBACK)
