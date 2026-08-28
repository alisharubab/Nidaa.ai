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


def rule_urgency(transcript: str) -> str:
    """Returns "critical" if any CRITICAL_RULE_TERMS hit (or the
    child/elderly + water-rise combination), else "info" as the rule
    engine's floor. TODO(CORE-19): implement term matching, case-insensitive,
    substring or fuzzy as appropriate for Roman Urdu spelling variance."""
    raise NotImplementedError


def blended_urgency(model_urgency: str, transcript: str) -> str:
    r_urgency = rule_urgency(transcript)
    return max(model_urgency, r_urgency, key=URGENCY_ORDER.index)
