# Stage 3: deterministic offline geocoding. docs/TRD.md section 4.5.
# Zero network calls by default, zero hallucination: a district either
# resolves to a real P-code or resolves to null. No middle state.

import csv
import json
import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process

DATA_DIR = Path(__file__).parent.parent.parent / "data"

FUZZY_ACCEPT_SCORE = 85  # raw rapidfuzz WRatio threshold, 0-100 scale
FUZZY_RATIO_GUARD = 70   # raw rapidfuzz plain-ratio floor, see _best_fuzzy_match()

# Common Urdu/Roman-Urdu geographic filler words that dilute or distort a
# fuzzy match if left in (e.g. "tehsil Johi mein" scoring worse against
# "Johi" than the bare word would, or a stray word coincidentally matching
# something unrelated). Stripped as whole words/phrases (word-boundaried),
# never mid-word, before any of exact/alias/fuzzy runs.
_STOP_WORDS = [
    "zila", "district", "tehsil", "shehar", "city", "gaon", "goth", "basti",
    "ke paas", "qareeb", "mein", "se", "road", "pul",
]
_STOP_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _STOP_WORDS) + r")\b"
)


def load_gazetteer(path: Path = DATA_DIR / "pak_gazetteer.csv") -> list[dict]:
    """Loads data/pak_gazetteer.csv (adm1_name,adm1_pcode,adm2_name,
    adm2_pcode,adm3_name,adm3_pcode,lat,lon) -- one row per tehsil."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_aliases(path: Path = DATA_DIR / "aliases.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(s: str) -> str:
    """Lowercase, strip diacritics/combining marks, collapse whitespace --
    docs/TRD.md 4.5 step 2. Applied to both the candidate string and the
    gazetteer/alias keys so "Dadu", " dadu ", and "DADU" all match the same
    entry."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    return re.sub(r"\s+", " ", s)


def _strip_stop_words(s: str) -> str:
    """Removes _STOP_WORDS (whole-word/phrase, not mid-word) from an
    already-normalized candidate string, then collapses the whitespace left
    behind. Only ever applied to the incoming candidate (location_raw /
    district_guess) -- never to district_index or alias keys, which are
    real place names, not free text, and have no filler words to strip."""
    stripped = _STOP_WORD_RE.sub(" ", s)
    return re.sub(r"\s+", " ", stripped).strip()


def build_district_index(gazetteer: list[dict], aliases: dict | None = None) -> dict:
    """The gazetteer has one row per tehsil (admin-3), but aliases.json and
    the LLM's district_guess operate at district (admin-2) level. Groups
    tehsil rows by district and averages their centroids as a practical
    district-level point -- docs/TRD.md 4.5: "Centroids come from the
    shapefile or, to stay dependency-light, from the gazetteer's own
    coordinate columns where present." Keyed by normalized adm2_name. Call
    once at startup, not per-request (rebuilding this per lookup would be
    wasteful -- it's the same ~577 rows every time).

    Also indexes individual tehsils (admin-3) by their own normalized name,
    pointing at the tehsil's own coordinates while still tagging the parent
    district's adm2_name/pcode -- so a message naming a specific town drops
    a pin on that town rather than the district centroid, without changing
    anything district-level (DDMA filters, WhatsApp readbacks, dedup) that
    reads adm2_name/pcode. A tehsil name is skipped, not indexed, if it's
    ambiguous, checked three ways: (1) collides with a DIFFERENT district's
    own name (e.g. Sahiwal is both a real district AND an unrelated tehsil
    of Sargodha), (2) is itself a tehsil name shared by more than one
    district (e.g. Khanpur names a tehsil in three different provinces), or
    (3) collides with an existing `aliases.json` key that points somewhere
    else (e.g. "naseerabad"/"nasir abad"/"dir" are all real tehsils whose
    normalized names happen to equal an alias hand-curated to mean a
    DIFFERENT district -- found via a full alias-table regression sweep
    after exact-match was reordered ahead of alias lookup, since that
    reordering is what made a colliding tehsil entry able to shadow the
    intended alias). `aliases` is optional only so callers/tests that
    genuinely don't have it yet can still build a district-only index;
    every real call site should pass it. Silently letting any of these
    collide would resolve a real place name to the WRONG district -- worse
    than the coarser-but-correct district centroid, and the same class of
    confident-but-wrong geocode this project hit before (the Muzaffargarh/
    Muzaffarabad case, docs/TRD.md 4.5). An ambiguous tehsil name just falls
    back to its own district-level entry, which is already unambiguous."""
    aliases = aliases or {}
    groups: dict[str, list[dict]] = {}
    for row in gazetteer:
        key = _normalize(row["adm2_name"])
        groups.setdefault(key, []).append(row)

    index = {}
    for key, rows in groups.items():
        lats = [float(r["lat"]) for r in rows]
        lons = [float(r["lon"]) for r in rows]
        index[key] = {
            "adm2_name": rows[0]["adm2_name"],
            "adm1_name": rows[0]["adm1_name"],
            "pcode": rows[0]["adm2_pcode"],
            "latitude": sum(lats) / len(lats),
            "longitude": sum(lons) / len(lons),
        }

    tehsil_districts: dict[str, set[str]] = {}
    for row in gazetteer:
        t_key = _normalize(row["adm3_name"])
        if t_key:
            tehsil_districts.setdefault(t_key, set()).add(row["adm2_name"])

    for row in gazetteer:
        t_key = _normalize(row["adm3_name"])
        d_key = _normalize(row["adm2_name"])
        if not t_key or t_key == d_key:
            continue  # same name as its own district -- the district entry already covers it
        if t_key in groups:
            continue  # collides with a DIFFERENT district's own name (e.g. Sahiwal)
        if len(tehsil_districts[t_key]) > 1:
            continue  # ambiguous: this tehsil name exists in more than one district
        alias_target = aliases.get(t_key)
        if alias_target is not None and _normalize(alias_target) != d_key:
            continue  # collides with an alias meaning a different district (e.g. naseerabad/nasir abad/dir)
        index[t_key] = {
            "adm2_name": row["adm2_name"],
            "adm1_name": row["adm1_name"],
            "pcode": row["adm2_pcode"],
            "latitude": float(row["lat"]),
            "longitude": float(row["lon"]),
        }

    return index


def _no_match() -> dict:
    return {
        "adm2_name": None, "adm1_name": None, "pcode": None,
        "latitude": None, "longitude": None,
        "geocode_method": "none", "geocode_score": None,
    }


def _try_cascade(candidate: str | None, district_index: dict, aliases: dict) -> dict | None:
    """One candidate string through exact -> alias -> fuzzy, tried first as
    typed and then again with geographic filler words stripped ("tehsil
    Johi mein" -> "johi") if the first attempt finds nothing. Returns None
    (not _no_match()) on failure so the caller can try a second candidate
    before giving up -- see geocode().

    Un-stripped is tried FIRST, not stripped-then-fallback-to-raw, because a
    handful of real tehsils (Lahore City, Faisalabad City, Hyderabad City,
    Multan City, Quetta City) literally contain a filler word ("city") as
    part of their own name -- stripping unconditionally before ever
    attempting an exact match would silently downgrade those to their
    district's coarser centroid for no reason, when the tehsil-precise
    exact match was sitting right there.

    Exact match is tried BEFORE alias lookup (reordered from the original
    alias-first cascade) because data/aliases.json has genuine name
    collisions: e.g. "Sahiwal" is a real district AND, separately, an
    unrelated tehsil of Sargodha that got aliased to "Sargodha" -- with
    alias checked first, that entry silently hijacked every mention of the
    real Sahiwal district before this fix. Aliases exist to catch spelling
    variants of a name that ISN'T already a literal, valid district name;
    when the candidate already exactly matches a real district, that's
    strictly more certain than a heuristic alias-table guess and should
    always win."""
    normalized = _normalize(candidate) if candidate else ""
    if not normalized:
        return None

    result = _cascade_attempt(normalized, district_index, aliases)
    if result is not None:
        return result

    stripped = _strip_stop_words(normalized)
    if stripped and stripped != normalized:
        return _cascade_attempt(stripped, district_index, aliases)
    return None


def _cascade_attempt(normalized: str, district_index: dict, aliases: dict) -> dict | None:
    """The actual exact -> alias -> fuzzy cascade against one already-
    normalized string. Split out of _try_cascade() so it can be run twice
    (raw, then stop-word-stripped) without duplicating the three stages."""
    # 1. Exact normalised match against a real district name.
    entry = district_index.get(normalized)
    if entry is not None:
        return {**entry, "geocode_method": "exact", "geocode_score": 1.0}

    # 2. Alias lookup (hand-curated Roman Urdu / Urdu-script spelling
    # variants -> canonical district name, data/aliases.json).
    alias_target = aliases.get(normalized)
    if alias_target is not None:
        entry = district_index.get(_normalize(alias_target))
        if entry is not None:
            return {**entry, "geocode_method": "alias", "geocode_score": 1.0}

    # 3. Fuzzy match, on SPACE-COLLAPSED strings. Plain WRatio is exploitable
    # by short-target suffix collisions in Pakistani toponyms: its partial-
    # ratio component can score a shared suffix on a SHORT target higher
    # than a correct but longer match -- "muzafar ghar" scored 85.5 against
    # "tor ghar" (matching only the shared standalone word "ghar") but only
    # 83.3 against the actually-correct "muzaffargarh" (just under the old
    # single-candidate threshold), which would confidently geocode a South
    # Punjab flood report to a mountain district in KP. Collapsing spaces
    # before comparing fixes BOTH sides at once: it removes the "ghar" word
    # boundary the wrong match was exploiting (WRatio 85.5 -> 75.0) while
    # correctly recognizing a stray/missing space in a compound name as the
    # minor difference it is (WRatio 83.3 -> 87.0) -- Roman Urdu spacing of
    # compound names ("Muzaffar Garh" vs "Muzaffargarh") isn't standardized,
    # so this is a real, common variation, not a loosened threshold.
    # Additionally guarded by a real (non-partial) fuzz.ratio >=
    # FUZZY_RATIO_GUARD, and checks the top few candidates (not just the
    # single best) so one suffix-inflated match can't block a correct
    # answer further down the ranking from ever being considered.
    collapsed_candidate = normalized.replace(" ", "")
    # Built defensively, not a plain dict comprehension: two DIFFERENT real
    # places can collapse to the same string (e.g. the Balochistan district
    # "Nasirabad" and an unrelated Kambar Shahdad Kot tehsil "Nasir Abad"),
    # same class of collision as build_district_index()'s tehsil guards. A
    # naive comprehension would silently let whichever key iterates last
    # shadow the other; ambiguous collapsed forms are excluded here instead
    # -- the exact-match stage above already resolves either spelling
    # correctly on its own, this only affects genuinely fuzzy/typo'd input.
    collapsed_to_key: dict[str, str] = {}
    ambiguous_collapsed: set[str] = set()
    for key in district_index.keys():
        c = key.replace(" ", "")
        if c in collapsed_to_key and collapsed_to_key[c] != key:
            ambiguous_collapsed.add(c)
        else:
            collapsed_to_key[c] = key
    for c in ambiguous_collapsed:
        collapsed_to_key.pop(c, None)
    matches = process.extract(collapsed_candidate, collapsed_to_key.keys(), scorer=fuzz.WRatio, limit=5)
    for collapsed_key, score, _ in matches:
        if score < FUZZY_ACCEPT_SCORE:
            break  # extract() is score-sorted descending -- nothing after this clears the bar either
        if fuzz.ratio(collapsed_candidate, collapsed_key) < FUZZY_RATIO_GUARD:
            continue
        entry = district_index[collapsed_to_key[collapsed_key]]
        # geocode_score is ALWAYS 0-1 (docs/TRD.md section 2 constraint
        # note) -- normalize the raw 0-100 WRatio before returning.
        return {**entry, "geocode_method": "fuzzy", "geocode_score": score / 100.0}

    return None


def geocode(location_raw: str | None, district_guess: str | None,
            district_index: dict, aliases: dict) -> dict:
    """Tries `location_raw` first (it may directly name a district, e.g.
    "Dadu"), then falls back to `district_guess` (the LLM's own coarser
    guess) if the raw text didn't resolve -- location_raw can be a longer
    phrase like "Dadu ke pass Johi" that the fuzzy matcher handles less
    reliably than a cleaner district-only guess. Returns _no_match() (all
    location fields NULL, method="none") if neither resolves -- that
    routes the ticket to the Unlocated queue, never an invented coordinate
    (hard rule 3, ../../CLAUDE.md).

    Returns {"adm2_name", "adm1_name", "pcode", "latitude", "longitude",
    "geocode_method", "geocode_score"}.
    """
    for candidate in (location_raw, district_guess):
        result = _try_cascade(candidate, district_index, aliases)
        if result is not None:
            return result
    return _no_match()
