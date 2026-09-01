"""DATA-07: generate the gold-set case directories and label.json files.

25 labelled evaluation cases per docs/TRD.md section 8:
  - a01..a15  audio (5 clean / 5 moderate / 5 severe)
  - t01..t10  text

Each case directory gets a label.json. The audio WAV files themselves are
NOT generated here:
  - a01..a10 must be real human voice-note recordings (phone, natural pace,
    Urdu) placed by hand into cases/aNN/audio.wav -- see data/gold_set/README.md
  - a11..a15 (severe noise, expected unintelligible) can be TTS + heavy noise,
    built by the README's edge-tts + degrade_audio.py recipe

Labels use the exact vocabularies of core/pipeline/extract.py
(intent/urgency Literals) so the DATA-10 eval script can compare directly.
P-codes are real district-level adm2 codes from data/pak_gazetteer.csv --
verified 2026-09-01, none invented.

Usage (from repo root):
    python tools/build_gold_set.py            # validate + (re)generate label.json files
    python tools/build_gold_set.py --check    # validate labels + verify audio files exist

Re-running is safe: label.json is overwritten, audio files are never touched.
"""

import json
import sys
from pathlib import Path

GOLD_DIR = Path(__file__).resolve().parent.parent / "data" / "gold_set" / "cases"

# (district, province, pcode) -- all from pak_gazetteer.csv adm2 rows
D = {
    "Dadu":                  ("Sindh", "PK703"),
    "Swat":                  ("Khyber Pakhtunkhwa", "PK532"),
    "Sukkur":                ("Sindh", "PK723"),
    "Jacobabad":             ("Sindh", "PK707"),
    "Larkana":               ("Sindh", "PK713"),
    "Kambar Shahdad Kot":    ("Sindh", "PK709"),
    "Multan":                ("Punjab", "PK622"),
    "Thatta":                ("Sindh", "PK727"),
    "Shikarpur":             ("Sindh", "PK720"),
    "Muzaffargarh":          ("Punjab", "PK623"),
    "Shaheed Benazir Abad":  ("Sindh", "PK719"),
    "Rajanpur":              ("Punjab", "PK629"),
    "Dera Ghazi Khan":       ("Punjab", "PK607"),
    "Khairpur":              ("Sindh", "PK711"),
    "Badin":                 ("Sindh", "PK701"),
    "Ghotki":                ("Sindh", "PK705"),
    "Charsadda":             ("Khyber Pakhtunkhwa", "PK506"),
}


def rec(district, intent, urgency, items=None, affected=None, casualties=None):
    prov, pcode = D[district]
    return {
        "district": district,
        "province": prov,
        "pcode": pcode,
        "intent": intent,
        "urgency": urgency,
        "items": [{"item": i} for i in (items or [])],
        "people_affected": affected,
        "casualties": casualties,
    }


def audio_case(cid, tier, source, script, expected):
    return {
        "id": cid, "modality": "audio", "noise_tier": tier, "source": source,
        "script": script, "text": None, "expected": expected,
    }


def text_case(cid, text, expected):
    return {
        "id": cid, "modality": "text", "noise_tier": None, "source": "human",
        "script": None, "text": text, "expected": expected,
    }


EXTRACTED = "extracted"

CASES = [
    # --- audio, clean tier: real human recordings -------------------------
    audio_case("a01", "clean", "human",
        "Dadu mein paani aur khane ki bohot zaroorat hai, log bhaage hue hain, jaldi madad pohnchani hai.",
        {"outcome": EXTRACTED, "records": [
            rec("Dadu", "resource_request", "high", ["water", "food"])]}),
    audio_case("a02", "clean", "human",
        "Swat mein nadi ka paani aaya hua hai, ek bacha doob gaya hai, waqt bohot kam hai.",
        {"outcome": EXTRACTED, "records": [
            rec("Swat", "incident_report", "critical", casualties=1)]}),
    audio_case("a03", "clean", "human",
        "Sukkur ke camp mein do sau log hain, dawai aur medical team foran chahiye.",
        {"outcome": EXTRACTED, "records": [
            rec("Sukkur", "resource_request", "critical", ["medicine"], affected=200)]}),
    audio_case("a04", "clean", "human",
        "Jacobabad se gaon jaane wali sarak paani mein doob gayi hai, koi raasta nahi bacha.",
        {"outcome": EXTRACTED, "records": [
            rec("Jacobabad", "infrastructure_damage", "high")]}),
    audio_case("a05", "clean", "human",
        "Salam, sab theek hai? Main bas check kar raha tha ke ye number kaam kar raha hai.",
        {"outcome": EXTRACTED, "records": [
            {"district": None, "province": None, "pcode": None,
             "intent": "non_actionable", "urgency": "info",
             "items": [], "people_affected": None, "casualties": None}]}),

    # --- audio, moderate noise: human recordings + noise mix --------------
    audio_case("a06", "moderate", "human",
        "Larkana mein paani ki level barh rahi hai, kashtiyan bhejein, log chatiyon par hain.",
        {"outcome": EXTRACTED, "records": [
            rec("Larkana", "resource_request", "critical", ["boat"])]}),
    audio_case("a07", "moderate", "human",
        "Kambar mein paani tezi se barh raha hai, logon ko khali karana zaroori hai.",
        {"outcome": EXTRACTED, "records": [
            rec("Kambar Shahdad Kot", "incident_report", "high")]}),
    audio_case("a08", "moderate", "human",
        "Multan ke camp mein bache aur kamble chahiye, sardi mein bachon ko thand lag rahi hai.",
        {"outcome": EXTRACTED, "records": [
            rec("Multan", "resource_request", "moderate", ["blanket", "shelter"])]}),
    audio_case("a09", "moderate", "human",
        "Thatta mein paanch sau log khane ke mohtaj hain, ration pohncha dein.",
        {"outcome": EXTRACTED, "records": [
            rec("Thatta", "resource_request", "high", ["food"], affected=500)]}),
    audio_case("a10", "moderate", "human",
        "Shikarpur mein school ki deewar paani se gir gayi hai, bachon ka imtihan multawi ho gaya hai.",
        {"outcome": EXTRACTED, "records": [
            rec("Shikarpur", "infrastructure_damage", "moderate")]}),

    # --- audio, severe noise: TTS acceptable, gate must give up ----------
    audio_case("a11", "severe", "tts", "(any script -- gate must reject)",
        {"outcome": "audio_unintelligible"}),
    audio_case("a12", "severe", "tts", "(any script -- gate must reject)",
        {"outcome": "audio_unintelligible"}),
    audio_case("a13", "severe", "tts", "(any script -- gate must reject)",
        {"outcome": "audio_unintelligible"}),
    audio_case("a14", "severe", "tts", "(any script -- gate must reject)",
        {"outcome": "audio_unintelligible"}),
    audio_case("a15", "severe", "tts", "(any script -- gate must reject)",
        {"outcome": "audio_unintelligible"}),

    # --- text cases --------------------------------------------------------
    text_case("t01",
        "Larkana mein paani chahiye, Sukkur mein khana chahiye, aur Multan mein log pareshan hain. Jaldi madad pohnchao.",
        {"outcome": EXTRACTED, "records": [
            rec("Larkana", "resource_request", "high", ["water"]),
            rec("Sukkur", "resource_request", "high", ["food"]),
            rec("Multan", "resource_request", "high")]}),
    text_case("t02",
        "Hamare ghar paani aa gaya hai, bachon ke liye khana nahi hai. Jagah ka pata main nahi bata sakta.",
        {"outcome": EXTRACTED, "records": [
            {"district": None, "province": None, "pcode": None,
             "intent": "resource_request", "urgency": "high",
             "items": [{"item": "food"}], "people_affected": None, "casualties": None}]}),
    text_case("t03",
        "مظفرگڑھ میں پانی خطرے کی حد پر ہے، لوگ مکان چھوڑ کر جا رہے ہیں، فوراً مدد بھیجیں۔",
        {"outcome": EXTRACTED, "records": [
            rec("Muzaffargarh", "resource_request", "critical")]}),
    text_case("t04",
        "Nawabshah mein teen din se bijli band hai, paani ki motor bhi nahi chal rahi.",
        {"outcome": EXTRACTED, "records": [
            rec("Shaheed Benazir Abad", "infrastructure_damage", "high")]}),
    text_case("t05",
        "Rajanpur mein bund tootne se teen log beh gaye hain, aur kai ghayal hain.",
        {"outcome": EXTRACTED, "records": [
            rec("Rajanpur", "incident_report", "critical", casualties=3)]}),
    text_case("t06",
        "Hello? Is anyone receiving this message? Testing one two three.",
        {"outcome": EXTRACTED, "records": [
            {"district": None, "province": None, "pcode": None,
             "intent": "non_actionable", "urgency": "info",
             "items": [], "people_affected": None, "casualties": None}]}),
    text_case("t07",
        "Dera Ghazi Khan mein mobile network aur bijli dono band hain, raasta bhi paani mein hai.",
        {"outcome": EXTRACTED, "records": [
            rec("Dera Ghazi Khan", "infrastructure_damage", "high")]}),
    text_case("t08",
        "Khairpur mein ek hazaar log saaf paani ke baghair hain, tanker bhejein.",
        {"outcome": EXTRACTED, "records": [
            rec("Khairpur", "resource_request", "high", ["water"], affected=1000)]}),
    text_case("t09",
        "Badin mein machhere apni kashtiyaan kho chuke hain, aur Ghotki mein zameen ke neeche paani aa raha hai. Dono jagah madad chahiye.",
        {"outcome": EXTRACTED, "records": [
            rec("Badin", "incident_report", "high"),
            rec("Ghotki", "incident_report", "high")]}),
    text_case("t10",
        "Charsadda mein pul toot gaya hai, gaariyan dono taraf phansi hui hain.",
        {"outcome": EXTRACTED, "records": [
            rec("Charsadda", "infrastructure_damage", "critical")]}),
]


def _validate():
    """Cross-check CASES against the gazetteer and the pipeline vocabularies.

    Labels are the DATA-10 contract -- a typo'd intent or a mismatched
    P-code would silently corrupt the benchmark, so this runs on every
    generation. Returns a list of human-readable error strings.
    """
    import csv

    root = Path(__file__).resolve().parent.parent
    gaz = {}
    with open(root / "data" / "pak_gazetteer.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            gaz[row["adm2_name"]] = row["adm2_pcode"]

    intents = {"resource_request", "incident_report", "infrastructure_damage", "non_actionable"}
    urgencies = {"critical", "high", "moderate", "info"}
    outcomes = {"extracted", "audio_unintelligible"}
    errors = []
    for case in CASES:
        cid = case["id"]
        exp = case["expected"]
        if exp["outcome"] not in outcomes:
            errors.append(f"{cid}: unknown outcome {exp['outcome']!r}")
        if case["modality"] == "text" and not case["text"]:
            errors.append(f"{cid}: text case has no text")
        if case["modality"] == "audio" and not case["script"]:
            errors.append(f"{cid}: audio case has no script")
        for r in exp.get("records", []):
            if r["intent"] not in intents:
                errors.append(f"{cid}: unknown intent {r['intent']!r}")
            if r["urgency"] not in urgencies:
                errors.append(f"{cid}: unknown urgency {r['urgency']!r}")
            if r["pcode"] is None:
                continue
            if r["district"] not in gaz:
                errors.append(f"{cid}: {r['district']!r} not in gazetteer")
            elif gaz[r["district"]] != r["pcode"]:
                errors.append(f"{cid}: {r['district']} pcode {r['pcode']} != gazetteer {gaz[r['district']]}")
    return errors


def main() -> int:
    errors = _validate()
    if errors:
        for e in errors:
            print(f"label error: {e}")
        return 1

    if "--check" in sys.argv:
        missing = []
        for case in CASES:
            if case["modality"] != "audio":
                continue
            case_dir = GOLD_DIR / case["id"]
            audio = list(case_dir.glob("audio.*")) if case_dir.exists() else []
            if not audio:
                missing.append(case["id"])
        if missing:
            print(f"missing audio files: {', '.join(missing)}")
            return 1
        print("all audio files present")
        return 0

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        case_dir = GOLD_DIR / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        label_path = case_dir / "label.json"
        label_path.write_text(
            json.dumps(case, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {label_path.relative_to(GOLD_DIR.parent.parent.parent)}")
    print(f"\n{len(CASES)} cases in {GOLD_DIR}")
    print("next: record the 10 human voice notes (a01-a10) -- see data/gold_set/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
