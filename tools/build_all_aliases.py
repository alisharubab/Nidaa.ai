# Build comprehensive aliases mapping for all Pakistan districts, tehsils, and Urdu variants.
# Supports both:
#  1. Default (Admin-2 District Centroid Target) - safe for baseline core geocoding
#  2. --tehsil-targets (Admin-3 Sub-district Precision) - for pinpoint town accuracy

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def _normalize(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    return re.sub(r"\s+", " ", s)

def generate_phonetic_variants(name):
    """Generates phonetic, spacing, and orthographic variations for a Roman Urdu place name."""
    norm = _normalize(name)
    if not norm or len(norm) < 3:
        return set()

    variants = set([norm])

    # 1. Spacing permutations
    if " " in norm:
        variants.add(norm.replace(" ", ""))
        variants.add(norm.replace(" ", "-"))
    if "-" in norm:
        variants.add(norm.replace("-", " "))
        variants.add(norm.replace("-", ""))

    # 2. Compound suffix splits (e.g. muzaffargarh -> muzaffar garh / muzafar ghar)
    suffixes = [
        ("garh", [" garh", " ghar", " gar", " gadh"]),
        ("ghar", [" ghar", " garh", " gar"]),
        ("pur", [" pur", " poor", " pore"]),
        ("abad", [" abad", " aabad"]),
        ("khel", [" khel", " xel"]),
        ("kot", [" kot", " kote"]),
        ("wala", [" wala"]),
        ("wali", [" wali"]),
        ("nagar", [" nagar"]),
        ("khas", [" khas"]),
        ("shah", [" shah"]),
        ("pattan", [" pattan", " patan"]),
        ("channu", [" channu", " chanu"]),
    ]

    for v in list(variants):
        for suf, replacements in suffixes:
            if v.endswith(suf) and not v.endswith(" " + suf):
                base = v[:-len(suf)].strip()
                if len(base) >= 3:
                    for rep in replacements:
                        variants.add(base + rep)
                        variants.add((base + rep).replace(" ", ""))

    # 3. Double consonant reductions and expansions
    double_consonants = ["ff", "tt", "kk", "dd", "ll", "mm", "nn", "ss", "pp", "bb", "rr"]
    for v in list(variants):
        for dc in double_consonants:
            if dc in v:
                variants.add(v.replace(dc, dc[0]))
            single = dc[0]
            if single in v and dc not in v and len(v) < 18:
                if single in ["f", "t", "k", "d", "n", "m", "s", "l"]:
                    variants.add(v.replace(single, dc, 1))

    # 4. Common vowel swaps and phonetic shifts
    for v in list(variants):
        if "e" in v:
            variants.add(v.replace("e", "i"))
            variants.add(v.replace("e", "a"))
        if "i" in v:
            variants.add(v.replace("i", "e"))
        if "u" in v:
            variants.add(v.replace("u", "o"))
            variants.add(v.replace("u", "oo"))
        if "oo" in v:
            variants.add(v.replace("oo", "u"))
        if "q" in v:
            variants.add(v.replace("q", "k"))
        if "k" in v and "q" not in v:
            variants.add(v.replace("k", "q", 1))
        if "kh" in v:
            variants.add(v.replace("kh", "x"))

    # 5. Prefixes (zila, district, tehsil)
    prefixed = set()
    for v in variants:
        prefixed.add(f"zila {v}")
        prefixed.add(f"district {v}")
        prefixed.add(f"tehsil {v}")

    all_variants = variants | prefixed
    return {_normalize(v) for v in all_variants if len(v) >= 3}


def build_aliases(tehsil_precision=False):
    with open(DATA_DIR / "pak_gazetteer.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    valid_districts = set(r["adm2_name"].strip() for r in rows)
    district_normalized_map = {_normalize(d): d for d in valid_districts}

    # High-priority base dictionary (never overwritten by heuristics)
    base_aliases = {}

    # Collision safety net for the CURATED maps below (URDU_MAP/TEHSIL_MAP).
    # Added after a real production bug: this script generated a "dir" ->
    # "Lower Dir" alias and "naseerabad"/"nasir abad" -> "Nasirabad" aliases
    # with no collision checking -- "Dir" is a real tehsil, but only of
    # Upper Dir; "Naseerabad"/"Nasir Abad" are real tehsils of Muzaffarabad
    # and Kambar Shahdad Kot respectively, not Nasirabad district. The
    # algorithmic layers further down already guard against a generated
    # variant colliding with a literal district name (`district_normalized_map`)
    # and against ambiguous multi-district tehsil names (`tehsil_counts[tehsil]
    # > 1`), but neither of those catches THIS pattern: a tehsil that
    # unambiguously belongs to exactly one district, hand-typed into a
    # DIFFERENT district's variant list by mistake. That can only happen in
    # a hand-curated entry -- the algorithmic generator always maps a
    # tehsil's own variants to that tehsil's own true district, so it can't
    # introduce this class of bug on its own.
    #
    # IMPORTANT: this check must ALSO gate which explicit URDU_MAP/TEHSIL_MAP
    # strings are allowed to seed generate_phonetic_variants() below (section
    # 3/4) -- that generator always includes its own input string in its
    # output (its first line is `variants = set([norm])`), so an unsafe
    # explicit_var re-enters the alias set through generated_district_aliases/
    # generated_tehsil_aliases even when base_aliases correctly rejected it.
    # Filtering only the curated-layer write and not the generator input was
    # tried first and confirmed NOT sufficient -- the bad alias came back
    # through the algorithmic layer regardless.
    tehsil_owner = {}
    for r in rows:
        t = _normalize(r["adm3_name"])
        if t:
            tehsil_owner.setdefault(t, set()).add(r["adm2_name"].strip())

    def _is_safe_curated(key, target):
        """True unless `key` is a real tehsil belonging to a specific
        district OTHER than `target` -- see the note above for why only
        this exact pattern needs a check here."""
        k = _normalize(key)
        if not k:
            return False
        owners = tehsil_owner.get(k)
        if owners and len(owners) == 1 and target not in owners and target in valid_districts:
            return False  # k is a real tehsil of a specific district, but target names a different one
        return True

    def safe_curated_set(target_dict, key, target):
        """Only writes key->target into a curated (URDU_MAP/TEHSIL_MAP) dict
        if _is_safe_curated() allows it."""
        k = _normalize(key)
        if k and _is_safe_curated(key, target):
            target_dict[k] = target

    # 1. Comprehensive Urdu and Roman variants for all 160 districts
    URDU_MAP = {
        # Punjab
        'Attock': ['اٹک', 'ضلع اٹک', 'attak', 'atock'],
        'Bahawalnagar': ['بہاولنگر', 'بہاول نگر', 'bahawal nagar', 'bahawalnagar'],
        'Bahawalpur': ['بہاولپور', 'بہاول پور', 'bahawal pur', 'bahawalpur'],
        'Bhakkar': ['بھکر', 'ضلع بھکر', 'bhakar'],
        'Chakwal': ['چکوال', 'ضلع چکوال', 'chakkwal'],
        'Chiniot': ['چنیوٹ', 'ضلع چنیوٹ', 'chiniote'],
        'Dera Ghazi Khan': ['ڈیرہ غازی خان', 'ڈی جی خان', 'dera ghazi khan', 'dg khan', 'd.g khan', 'd.g. khan', 'dgk', 'deraghazikhan', 'd g khan'],
        'Faisalabad': ['فیصل آباد', 'فیصل اباد', 'لائلپور', 'faisal abad', 'lyallpur', 'faisalabad'],
        'Gujranwala': ['گوجرانوالہ', 'گوجرانوالا', 'gujran wala', 'gujranwala'],
        'Gujrat': ['گجرات', 'ضلع گجرات', 'gujraat'],
        'Hafizabad': ['حافظ آباد', 'حافظ اباد', 'hafiz abad', 'hafizabad'],
        'Jhang': ['جھنگ', 'ضلع جھنگ', 'jhang'],
        'Jhelum': ['جہلم', 'ضلع جہلم', 'jehlum'],
        'Kasur': ['قصور', 'ضلع قصور', 'qasoor', 'qasur', 'kasoor'],
        'Khanewal': ['خانیوال', 'ضلع خانیوال', 'khane wal', 'khanaywal'],
        'Khushab': ['خوشاب', 'ضلع خوشاب', 'khushaab'],
        'Lahore': ['لاہور', 'ضلع لاہور', 'lhr', 'lahor'],
        'Leiah': ['لیہ', 'لیا', 'لہیہ', 'ضلع لیہ', 'layyah', 'layya', 'leiah', 'liah', 'lia'],
        'Lodhran': ['لودھراں', 'ضلع لودھراں', 'lodhran'],
        'Mandi Bahauddin': ['منڈی بہاؤالدین', 'منڈی بہاؤ الدین', 'mandi bahauddin', 'mandi baha ud din', 'mb din', 'mbdin'],
        'Mianwali': ['میانوالی', 'ضلع میانوالی', 'mian wali'],
        'Multan': ['ملتان', 'ضلع ملتان', 'multaan'],
        'Muzaffargarh': ['مظفر گڑھ', 'مظفرگڑھ', 'ضلع مظفر گڑھ', 'muzaffar garh', 'muzaffargarh', 'muzafargarh', 'muzafar ghar', 'muzaffar ghar', 'muzafer ghar', 'muzaffer garh', 'muzaffar gadh', 'muzafar gadh'],
        'Nankana Sahib': ['ننکانہ صاحب', 'ننکانہ', 'nankana sahib', 'nankana'],
        'Narowal': ['نارووال', 'ضلع نارووال', 'naro wal', 'narowaal'],
        'Okara': ['اوکاڑہ', 'اوکاڑا', 'ضلع اوکاڑہ', 'okaara'],
        'Pakpattan': ['پاکپتن', 'پاک پتن', 'pak pattan', 'pakpattan', 'pakpatan'],
        'Rahim Yar Khan': ['رحیم یار خان', 'آر وائی خان', 'rahim yar khan', 'rahimyarkhan', 'ry khan', 'r.y. khan', 'rykhan', 'ryk'],
        'Rajanpur': ['راجن پور', 'راجنپور', 'rajan pur', 'rajanpur', 'rajanpoor', 'rajan poor'],
        'Rawalpindi': ['راولپنڈی', 'راول پنڈی', 'پنڈی', 'rawalpindi', 'rawal pindi', 'pindi', 'rwp'],
        'Sahiwal': ['ساہیوال', 'ضلع ساہیوال', 'منٹگمری', 'sahiwal', 'montgomery'],
        'Sargodha': ['سرگودھا', 'ضلع سرگودھا', 'sargodha'],
        'Sheikhupura': ['شیخوپورہ', 'شیخوپورا', 'ضلع شیخوپورہ', 'sheikhupura', 'sheikhoopura', 'sheikhupura'],
        'Sialkot': ['سیالکوٹ', 'ضلع سیالکوٹ', 'sial kot', 'sealkot'],
        'Toba Tek Singh': ['ٹوبہ ٹیک سنگھ', 'ٹوبہ', 'toba tek singh', 'toba', 'tts', 'toba teksingh'],
        'Vehari': ['وہاڑی', 'ضلع وہاڑی', 'vihari', 'vehaari'],

        # Sindh
        'Badin': ['بدین', 'ضلع بدین', 'baadin', 'badin'],
        'Central Karachi': ['کراچی وسطی', 'وسطی کراچی', 'کراچی سنٹرل', 'central karachi'],
        'Dadu': ['دادو', 'ڈاڈو', 'daadu', 'dadoo', 'dadu'],
        'East Karachi': ['کراچی شرقی', 'شرقی کراچی', 'کراچی ایسٹ', 'east karachi'],
        'Ghotki': ['گھوٹکی', 'ضلع گھوٹکی', 'ghotki', 'ghoki'],
        'Hyderabad': ['حیدرآباد', 'حیدر اباد', 'hyderabad', 'hyder abad', 'hyd'],
        'Jacobabad': ['جیکب آباد', 'جیکب اباد', 'جیکبہ', 'جیکبہ بابات', 'jacobabad', 'jakobabad', 'jacob abad', 'jikba', 'jikba babat'],
        'Jamshoro': ['جامشورو', 'جام شورو', 'jamshuro', 'jam shoro', 'jamshoro'],
        'Kambar Shahdad Kot': ['قمبر شہداد کوٹ', 'قمبر', 'کمبر', 'شہداد کوٹ', 'قمبر شہدادکوٹ', 'qambar shahdadkot', 'kamber shahdadkot', 'shahdadkot', 'qambar', 'kambar', 'qambar shahdad kot'],
        'Kashmore': ['کشمور', 'قشمور', 'kashmore', 'kashmor', 'qashmore', 'kandhkot'],
        'Khairpur': ['خیرپور', 'خیر پور', 'khairpur', 'khairpoor', 'khairpur mirs', 'xairpur'],
        'Korangi Karachi': ['کورنگی', 'کراچی کورنگی', 'korangi'],
        'Larkana': ['لاڑکانہ', 'لاڑکانو', 'ضلع لاڑکانہ', 'larkana', 'larkano'],
        'Malir Karachi': ['ملیر', 'کراچی ملیر', 'malir'],
        'Matiari': ['مٹیاری', 'ضلع مٹیاری', 'matiari', 'matiyari'],
        'Mirpur Khas': ['میرپور خاص', 'میر پور خاص', 'میرپورخاص', 'mirpur khas', 'mirpurkhas', 'mir pur khas', 'meerpur khas'],
        'Naushahro Feroze': ['نوشہرو فیروز', 'نوشہروفیروز', 'naushahro feroze', 'naushahroferoze', 'naushero feroze', 'nawabshah feroze', 'noshero feroz'],
        'Sanghar': ['سانگھڑ', 'ضلع سانگھڑ', 'sanghar', 'sangher'],
        'Shaheed Benazir Abad': ['شہید بینظیر آباد', 'شہید بے نظیر آباد', 'نواب شاہ', 'نوابشاہ', 'بینظیر آباد', 'shaheed benazir abad', 'shaheed benazirabad', 'benazirabad', 'nawabshah', 'nawab shah', 'sba'],
        'Shikarpur': ['شکارپور', 'ضلع شکارپور', 'shikarpur', 'shikaarpur', 'shikar pur', 'shikarpoor'],
        'South Karachi': ['کراچی جنوبی', 'جنوبی کراچی', 'کراچی ساؤتھ', 'کراچی', 'karachi', 'khi'],
        'Sujawal': ['سجاول', 'ضلع سجاول', 'sujawal', 'sujaawal'],
        'Sukkur': ['سکھر', 'سخر', 'سکر', 'سکھر بیراج', 'sukkur', 'sakkhar', 'sukker', 'sukhar', 'sukhur', 'sakkar'],
        'Tando Allahyar': ['ٹنڈو الہ یار', 'ٹنڈو اللہ یار', 'ٹنڈوالہ یار', 'tando allahyar', 'tando allah yaar'],
        'Tando Muhammad Khan': ['ٹنڈو محمد خان', 'ٹنڈو محمدخان', 'tando muhammad khan', 'tmkhan', 'tm khan'],
        'Tharparkar': ['تھرپارکر', 'تھر پارکر', 'تھر', 'tharparkar', 'tharparker', 'thar parkar', 'thar'],
        'Thatta': ['ٹھٹھہ', 'ٹھٹہ', 'thatta', 'thata'],
        'Umer Kot': ['عمرکوٹ', 'عمر کوٹ', 'umer kot', 'umarkot', 'umerkot', 'amarkot'],
        'West Karachi': ['کراچی غربی', 'غربی کراچی', 'کراچی ویسٹ', 'west karachi'],

        # Balochistan
        'Awaran': ['آواران', 'اواران', 'ضلع آواران', 'awaran'],
        'Barkhan': ['بارکھان', 'ضلع بارکھان', 'barkhan'],
        'Chagai': ['چاغی', 'ضلع چاغی', 'chagai'],
        'Chaman': ['چمن', 'ضلع چمن', 'chaman'],
        'Dera Bugti': ['ڈیرہ بگٹی', 'dera bugti', 'derabugti'],
        'Duki': ['دوکی', 'ڈکی', 'ضلع دوکی', 'duki'],
        'Gwadar': ['گوادر', 'ضلع گوادر', 'gwadar'],
        'Harnai': ['ہرنائی', 'ضلع ہرنائی', 'harnai'],
        'Jaffarabad': ['جعفر آباد', 'جعفرآباد', 'jaffarabad', 'jafarabad', 'jaffar abad'],
        'Jhal Magsi': ['جھل مگسی', 'جھلمگسی', 'jhal magsi', 'jhalmagsi', 'jhal magsee'],
        'Kachhi': ['کچھی', 'بولان', 'kachhi', 'bolan'],
        'Kalat': ['قلات', 'ضلع قلات', 'kalat', 'kalaat', 'qalat'],
        'Kech': ['کیچ', 'تربت', 'kech', 'turbat'],
        'Kharan': ['خاران', 'ضلع خاران', 'kharan'],
        'Khuzdar': ['خضدار', 'ضلع خضدار', 'khuzdar', 'khozdaar', 'khozdar'],
        'Killa Abdullah': ['قلعہ عبداللہ', 'قلعہ عبد اللہ', 'killa abdullah', 'qila abdullah'],
        'Killa Saifullah': ['قلعہ سیف اللہ', 'قلعہ سیفاللہ', 'killa saifullah', 'qila saifullah', 'kila saifullah'],
        'Kohlu': ['کوہلو', 'ضلع کوہلو', 'kohlu'],
        'Lasbela': ['لسبیلہ', 'لس بیلہ', 'lasbela', 'las bela'],
        'Lehri': ['لہڑی', 'ضلع لہڑی', 'lehri'],
        'Loralai': ['لورالائی', 'ضلع لورالائی', 'loralai'],
        'Mastung': ['مستونگ', 'ضلع مستونگ', 'mastung'],
        'Musakhel': ['موسیٰ خیل', 'موسی خیل', 'ضلع موسی خیل', 'musakhel', 'musa khel'],
        'Nasirabad': ['نصیر آباد', 'نصیرآباد', 'nasirabad', 'naseerabad', 'nasir abad'],
        'Nushki': ['نوشکی', 'ضلع نوشکی', 'nushki'],
        'Panjgur': ['پنجگور', 'ضلع پنجگور', 'panjgur'],
        'Pishin': ['پشین', 'ضلع پشین', 'pishin'],
        'Quetta': ['کوئٹہ', 'ضلع کوئٹہ', 'quetta', 'qta', 'kwetta'],
        'Shaheed Sikandarabad': ['شہید سکندر آباد', 'سوراب', 'surab', 'shaheed sikandarabad'],
        'Sherani': ['شیرانی', 'ضلع شیرانی', 'sherani'],
        'Sibi': ['سبی', 'ضلع سبی', 'sibi', 'sibbi'],
        'Sohbatpur': ['صحبت پور', 'صحبتپور', 'ضلع صحبت پور', 'sohbatpur', 'sohbat pur'],
        'Washuk': ['واشک', 'ضلع واشک', 'washuk'],
        'Zhob': ['ژوب', 'ضلع ژوب', 'zhob'],
        'Ziarat': ['زیارت', 'ضلع زیارت', 'ziarat'],

        # Khyber Pakhtunkhwa
        'Abbottabad': ['ایبٹ آباد', 'ایبٹ اباد', 'ضلع ایبٹ آباد', 'abbottabad', 'abbotabad', 'abbott abad'],
        'Bajaur': ['باجوڑ', 'ضلع باجوڑ', 'bajaur'],
        'Bannu': ['بنوں', 'ضلع بنوں', 'bannu', 'banu'],
        'Batagram': ['بٹگرام', 'ضلع بٹگرام', 'batagram', 'battagram'],
        'Buner': ['بونیر', 'ضلع بونیر', 'buner'],
        'Charsadda': ['چارسدہ', 'ضلع چارسدہ', 'charsadda', 'charsada'],
        'Chitral Lower': ['چترال', 'لوئر چترال', 'چترال زیریں', 'ضلع چترال', 'lower chitral', 'chitral'],
        'Chitral Upper': ['اپر چترال', 'چترال بالا', 'upper chitral'],
        'D. I. Khan': ['ڈی آئی خان', 'ڈیرہ اسماعیل خان', 'di khan', 'd.i.khan', 'd. i. khan', 'd.i khan', 'dikhan', 'd i khan', 'dera ismail khan', 'dik', 'dera ismael khan'],
        'Hangu': ['ہنگو', 'ضلع ہنگو', 'hangu'],
        'Haripur': ['ہری پور', 'ہریپور', 'ضلع ہری پور', 'haripur', 'hari pur'],
        'Karak': ['کرک', 'ضلع کرک', 'karak'],
        'Khyber': ['خیبر', 'ضلع خیبر', 'khyber'],
        'Kohat': ['کوہاٹ', 'ضلع کوہاٹ', 'kohat'],
        'Kohistan Lower': ['لوئر کوہستان', 'کوہستان زیریں', 'lower kohistan'],
        'Kohistan Upper': ['اپر کوہستان', 'کوہستان بالا', 'upper kohistan'],
        'Kolai Palas Kohistan': ['کولئی پالس', 'کولئی پالس کوہستان', 'kolai palas'],
        'Kurram': ['کرم', 'ضلع کرم', 'kurram'],
        'Lakki Marwat': ['لکی مروت', 'ضلع لکی مروت', 'lakki marwat'],
        'Lower Dir': ['لوئر دیر', 'دیر زیریں', 'دیر', 'lower dir', 'dir lower', 'dir'],
        'Malakand': ['مالاکنڈ', 'ملاکنڈ', 'malakand'],
        'Mansehra': ['مانسہرہ', 'ضلع مانسہرہ', 'mansehra'],
        'Mardan': ['مردان', 'ضلع مردان', 'mardan'],
        'Mohmand': ['مہمند', 'ضلع مہمند', 'mohmand'],
        'North Waziristan': ['شمالی وزیرستان', 'north waziristan'],
        'Nowshera': ['نوشہرہ', 'ضلع نوشہرہ', 'nowshera', 'nowshehra', 'naushera'],
        'Orakzai': ['اورکزئی', 'ضلع اورکزئی', 'orakzai'],
        'Peshawar': ['پشاور', 'ضلع پشاور', 'peshawar', 'pesh', 'psh'],
        'Shangla': ['شانگلہ', 'ضلع شانگلہ', 'shangla'],
        'South Waziristan': ['جنوبی وزیرستان', 'south waziristan', 'waziristan'],
        'Swabi': ['صوابی', 'ضلع صوابی', 'swabi'],
        'Swat': ['سوات', 'ضلع سوات', 'swat', 'swaat'],
        'Tank': ['ٹانک', 'ضلع ٹانک', 'tank', 'taank'],
        'Tor Ghar': ['تور غر', 'تورغر', 'کالا ڈھاکہ', 'tor ghar', 'torghar', 'kala dhaka'],
        'Upper Dir': ['اپر دیر', 'دیر بالا', 'upper dir', 'dir upper'],

        # Azad Kashmir
        'Bagh': ['باغ', 'ضلع باغ', 'bagh'],
        'Bhimber': ['بھمبر', 'ضلع بھمبر', 'bhimber'],
        'Haveli': ['حویلی', 'ضلع حویلی', 'haveli'],
        'Jhelum Valley': ['جہلم ویلی', 'jhelum valley'],
        'Kotli': ['کوٹلی', 'ضلع کوٹلی', 'kotli'],
        'Mirpur': ['میرپور', 'ضلع میرپور', 'mirpur'],
        'Muzaffarabad': ['مظفر آباد', 'مظفرآباد', 'ضلع مظفر آباد', 'muzaffarabad', 'muzaffar abad', 'muzafarabad'],
        'Neelum': ['نیلم', 'وادی نیلم', 'neelum', 'neelum valley'],
        'Poonch': ['پونچھ', 'راولاکوٹ', 'راولا کوٹ', 'poonch', 'rawalakot'],
        'Sudhnoti': ['سدھنوتی', 'پلندری', 'sudhnoti', 'pallandri'],

        # Gilgit Baltistan
        'Astore': ['استور', 'ضلع استور', 'astore'],
        'Darel': ['داریل', 'ضلع داریل', 'darel'],
        'Diamir': ['دیامر', 'ضلع دیامر', 'diamir'],
        'Ghanche': ['گانچھے', 'ghanche'],
        'Ghizer': ['غذر', 'ضلع غذر', 'ghizer'],
        'Gilgit': ['گلگت', 'ضلع گلگت', 'gilgit'],
        'Gupis-Yasin': ['گوپس یاسین', 'gupis yasin', 'gupis-yasin'],
        'Hunza': ['ہنزہ', 'hunza'],
        'Kharmang': ['کھرمنگ', 'kharmang'],
        'Nagar': ['نگر', 'ضلع نگر', 'nagar'],
        'Rondu': ['روندو', 'ضلع روندو', 'rondu'],
        'Shigar': ['شگر', 'ضلع شگر', 'shigar'],
        'Skardu': ['سکردو', 'ضلع سکردو', 'skardu'],
        'Tangir': ['تانگیر', 'ضلع تانگیر', 'tangir'],

        # Islamabad
        'Islamabad': ['اسلام آباد', 'اسلام اباد', 'اسلاماباد', 'islamabad', 'isloo', 'isb']
    }

    # Populate explicit district aliases
    for dist, var_list in URDU_MAP.items():
        if dist not in valid_districts:
            continue
        for var in var_list:
            safe_curated_set(base_aliases, var, dist)

    # 2. Tehsils explicit mapping (Curated Urdu + transliterations)
    TEHSIL_MAP = {
        'Mian Channu': ['میاں چنوں', 'میاں چنو', 'mian channu', 'mianchannu', 'mian chanu'],
        'Kabirwala': ['کبیروالا', 'کبیر والا', 'kabirwala', 'kabir wala'],
        'Jahanian': ['جہانیاں', 'jahanian'],
        'Johi': ['جوہی', 'johi'],
        'Mehar': ['میہڑ', 'mehar'],
        'Khairpur Nathan Shah': ['خیرپور ناتھن شاہ', 'kn shah', 'k n shah', 'k.n. shah'],
        'Rohri': ['روہڑی', 'rohri'],
        'Pano Aqil': ['پنو عاقل', 'pano aqil', 'panoaqil'],
        'Kotri': ['کوٹری', 'کوٹری بیراج', 'kotri'],
        'Sehwan': ['سیہون', 'sehwan', 'sehwan sharif'],
        'Hub': ['حب', 'hub'],
        'Bela': ['بیلہ', 'bela'],
        'Uthal': ['اوٹھل', 'uthal'],
        'Winder': ['وندر', 'winder'],
        'Sui': ['سوئی', 'sui'],
        'Taunsa': ['تونسہ', 'taunsa', 'taunsa sharif'],
        'Fazilpur': ['فاضل پور', 'fazilpur', 'fazil pur'],
        'Rojhan': ['روجھان', 'rojhan', 'rojhaan'],
        'Jampur': ['جام پور', 'jampur', 'jam pur'],
        'Mithi': ['مٹھی', 'mithi'],
        'Islamkot': ['اسلام کوٹ', 'islamkot', 'islam kot'],
        'Nagarparkar': ['نگر پارکر', 'nagarparkar', 'nagar parkar'],
        'Diplo': ['ڈپلو', 'diplo'],
        'Thul': ['ٹھل', 'thul'],
        'Garhi Khairo': ['گڑھی خیرو', 'garhi khairo'],
        'Kandhkot': ['کندھ کوٹ', 'kandhkot', 'kandh kot'],
        'Kot Addu': ['کوٹ ادو', 'کوٹ ادّو', 'kot addu', 'kotaddu', 'kot adu'],
        'Alipur': ['علی پور', 'alipur', 'ali pur', 'alipoor'],
        'Jatoi': ['جتوئی', 'jatoi'],
        'Daharki': ['ڈہرکی', 'daharki'],
        'Mirpur Mathelo': ['میرپور ماتھیلو', 'mirpur mathelo'],
        'Ubauro': ['اوباڑو', 'ubauro'],
        'Moro': ['مورو', 'moro'],
        'Kandiaro': ['کنڈیارو', 'kandiaro'],
        'Shahdadpur': ['شہدادپور', 'shahdadpur', 'shahdad pur'],
        'Tando Adam': ['ٹنڈو آدم', 'tando adam'],
        'Khipro': ['کھپرو', 'khipro'],
        'Matli': ['ماتلی', 'matli'],
        'Gharo': ['گھارو', 'gharo'],
        'Keti Bandar': ['کیٹی بندر', 'keti bandar'],
        'Usta Muhammad': ['اوستہ محمد', 'usta muhammad'],
        'Dera Allah Yar': ['ڈیرہ اللہ یار', 'dera allah yar'],
        'Dera Murad Jamali': ['ڈیرہ مراد جمالی', 'dera murad jamali'],
        'Turbat': ['تربت', 'turbat'],
        'Pasni': ['پسنی', 'pasni'],
        'Ormara': ['اورماڑہ', 'ormara'],
        'Chilas': ['چلاس', 'chilas'],
        'Parachinar': ['پاراچنار', 'parachinar'],
        'Balakot': ['بالاکوٹ', 'balakot', 'bala kot'],
        'Timergara': ['تیمرگرہ', 'timergara'],
        'Mingora': ['مینگورہ', 'mingora'],
    }

    # Keyed by space-collapsed normalized name, not the raw string: several
    # TEHSIL_MAP keys below don't exactly match the gazetteer's own spelling
    # ("Balakot" here vs. "Bala Kot" in the CSV; "Sehwan"/"Fazilpur"/"Winder"/
    # "Gharo"/"Keti Bandar"/"Turbat" don't match under any spacing at all --
    # they may not exist as a distinct adm3 row in this 577-row gazetteer).
    # A plain dict .get(teh, teh) silently fell back to using the TEHSIL_MAP
    # key ITSELF as the target on a miss -- a tehsil-shaped string being
    # written into what must always be a real district name, breaking every
    # var under that entry (confirmed: they all resolved to `none` end to
    # end through geocode(), a safe failure, but a silent, needless one).
    tehsil_to_district = {}
    for r in rows:
        k = r["adm3_name"].strip().lower().replace(" ", "")
        tehsil_to_district[k] = r["adm2_name"].strip()

    # Explicit tehsil mappings
    for teh, var_list in TEHSIL_MAP.items():
        if tehsil_precision:
            target = teh
        else:
            target = tehsil_to_district.get(teh.strip().lower().replace(" ", ""))
            if target is None:
                continue  # tehsil not found in the gazetteer under any spelling -- skip, don't guess
        for var in var_list:
            safe_curated_set(base_aliases, var, target)

    # 3. Build Algorithmic Variations for ALL 160 Districts
    generated_district_aliases = {}
    for dist in valid_districts:
        variants = generate_phonetic_variants(dist)
        for explicit_var in URDU_MAP.get(dist, []):
            if _is_safe_curated(explicit_var, dist):
                variants.update(generate_phonetic_variants(explicit_var))
        for v in variants:
            generated_district_aliases[v] = dist

    # 4. Build Algorithmic Variations for ALL 573 Tehsils
    generated_tehsil_aliases = {}
    tehsil_counts = {}
    for r in rows:
        t = r["adm3_name"].strip()
        tehsil_counts[t] = tehsil_counts.get(t, 0) + 1

    for r in rows:
        tehsil = r["adm3_name"].strip()
        district = r["adm2_name"].strip()
        target = tehsil if tehsil_precision else district

        # If tehsil name is ambiguous across multiple districts (e.g. Khanpur), skip heuristic expansion
        if tehsil_counts[tehsil] > 1:
            continue

        variants = generate_phonetic_variants(tehsil)
        for explicit_var in TEHSIL_MAP.get(tehsil, []):
            if _is_safe_curated(explicit_var, target):
                variants.update(generate_phonetic_variants(explicit_var))

        for v in variants:
            generated_tehsil_aliases[v] = target

    # 5. Assembly with Strict Collision Guards
    final_aliases = {}

    # Layer 3 vs 4 collision guard: the two algorithmic layers are generated
    # completely independently (one from each district's canonical name and
    # explicit variants, the other from each tehsil's), and a spacing/suffix
    # split of a district's OWN name can coincidentally produce the same
    # string as a real, different tehsil's own name -- found via a real
    # case: splitting "Nasirabad" (the district) on its "abad" suffix
    # produces "nasir abad", which is ALSO the literal name of an unrelated
    # tehsil in Kambar Shahdad Kot. Blindly letting one layer win (the
    # original code let Layer 3 always overwrite Layer 4) silently prefers
    # whichever layer happens to run last, not whichever is actually
    # correct. Any key both layers agree on is fine either way; any key
    # they DISAGREE on is a genuine ambiguity and dropped from both, same
    # "unindexed rather than guessed" principle as every other collision
    # guard in this file.
    ambiguous_layer_keys = {
        k for k, v in generated_district_aliases.items()
        if k in generated_tehsil_aliases and generated_tehsil_aliases[k] != v
    }

    # Layer 4: Generated Tehsil Aliases
    for k, v in generated_tehsil_aliases.items():
        if k not in district_normalized_map and k not in ambiguous_layer_keys:
            final_aliases[k] = v

    # Layer 3: Generated District Aliases
    for k, v in generated_district_aliases.items():
        if k not in district_normalized_map and k not in ambiguous_layer_keys:
            final_aliases[k] = v

    # Layer 2: Curated Base Aliases (always wins over heuristics)
    for k, v in base_aliases.items():
        if k not in district_normalized_map:
            final_aliases[k] = v

    # Layer 1: Real District names (self-identity guard, remove self-alias)
    for norm_d, real_d in district_normalized_map.items():
        if norm_d in final_aliases:
            del final_aliases[norm_d]

    # Clean up empty keys and self-mappings
    cleaned = {}
    for k, v in final_aliases.items():
        if not k or len(k) < 3:
            continue
        if k == _normalize(v):
            continue
        cleaned[k] = v

    return cleaned


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tehsils", action="store_true", help="Set alias targets to specific tehsils (requires updated geocode.py)")
    args = parser.parse_args()

    mode_name = "Tehsil Sub-district Precision" if args.tehsils else "District Centroid (Default)"
    print(f"Building aliases in mode: {mode_name}")
    data = build_aliases(tehsil_precision=args.tehsils)

    output_path = DATA_DIR / "aliases.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Successfully wrote {len(data)} aliases to {output_path}!")
