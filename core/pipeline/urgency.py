# Stage 4: blended urgency scoring. docs/TRD.md section 4.6.
# final_urgency = max(model_urgency, rule_urgency) — rules can only escalate,
# never de-escalate, so a model quirk can't silently downgrade a
# life-threatening message.

URGENCY_ORDER = ["info", "moderate", "high", "critical"]

# Terms/phrases that force urgency to "critical" regardless of model output.
CRITICAL_RULE_TERMS = [
    # casualty / injury
    "zakhmi", "hospital", "saans", "dawai",
    # glossary-derived critical phrases (docs/TRD.md section 5)
    "halat ghair ha", "doobne wale hain", "chhat gir rahi hai",
    "phansay huay hain",
]

# The "child or elderly plus water-rise terms" compound rule (docs/TRD.md
# 4.6) -- neither list alone forces critical, only their combination
# (a message just mentioning children, or just mentioning rising water,
# isn't automatically critical; both together describes a specific
# drowning-risk scenario the single-term list doesn't otherwise catch).
CHILD_ELDERLY_TERMS = ["bachay", "bacha", "bachon", "bachche", "boorha", "boodha", "buzurg"]
WATER_RISE_TERMS = ["paani charh", "paani barh", "paani ghus", "seelab", "paani ghar mein"]


def _contains_any(text: str, terms: list[str]) -> bool:
    text_lower = text.lower()
    return any(term in text_lower for term in terms)


def rule_urgency(transcript: str) -> str:
    """Returns "critical" if any CRITICAL_RULE_TERMS hit, or if both a
    child/elderly term AND a water-rise term are present, else "info" as
    the rule engine's floor (it never asserts "high"/"moderate" itself --
    those distinctions are left to the model; the rule engine's only job
    is to force an upgrade to critical when it's confident, never a
    downgrade -- see blended_urgency()).

    Matching is plain case-insensitive substring search, not fuzzy --
    deliberately simple and predictable for a safety-critical rule engine.
    Roman Urdu spelling variance (e.g. "zakhmi" vs "zakmi") is a real gap
    this doesn't cover; widening term lists in this file is the intended
    way to extend it, not adding fuzzy matching that could also make it
    accidentally MISS a term it currently would have string-matched.
    """
    if not transcript:
        return "info"
    if _contains_any(transcript, CRITICAL_RULE_TERMS):
        return "critical"
    if _contains_any(transcript, CHILD_ELDERLY_TERMS) and _contains_any(transcript, WATER_RISE_TERMS):
        return "critical"
    return "info"


def blended_urgency(model_urgency: str, transcript: str) -> str:
    r_urgency = rule_urgency(transcript)
    return max(model_urgency, r_urgency, key=URGENCY_ORDER.index)
