# Stage 3: deterministic offline geocoding. docs/TRD.md section 4.5.
# Zero network calls by default, zero hallucination: a district either
# resolves to a real P-code or resolves to null. No middle state.

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"

FUZZY_ACCEPT_SCORE = 85


def load_gazetteer(path: Path = DATA_DIR / "pak_gazetteer.csv") -> list[dict]:
    """Loads data/pak_gazetteer.csv (adm1_name,adm1_pcode,adm2_name,
    adm2_pcode,adm3_name,adm3_pcode,lat,lon). TODO(CORE-18): call this once
    at startup (main.py), not per-request."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_aliases(path: Path = DATA_DIR / "aliases.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def geocode(location_raw: str, gazetteer: list[dict], aliases: dict) -> dict:
    """Matching cascade, in order, first hit wins:
      1. alias lookup (aliases.json)               -> method="alias",  score=1.0
      2. exact normalised match (lowercase/strip)   -> method="exact",  score=1.0
      3. rapidfuzz.process.extractOne, WRatio >= 85 -> method="fuzzy",  score=<score>
      4. no match                                    -> method="none", lat/lon/pcode = None

    Returns {"adm2_name", "adm1_name", "pcode", "latitude", "longitude",
    "geocode_method", "geocode_score"}.

    TODO(CORE-18): implement the cascade. A "none" result routes the ticket
    to the Unlocated Alerts queue and fires the location_missing reply
    template — never invent coordinates.
    """
    raise NotImplementedError
