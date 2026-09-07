# Tehsil-Level (Admin-3) Coordinate Precision Upgrade

## 1. Overview
In the initial MVP, all tickets within a district shared the district centroid coordinates. For large districts (e.g. Khanewal, Dadu, Sukkur, Lasbela, Rajanpur), towns and tehsils located 40-80 km apart stacked on the exact same map coordinates.

This upgrade gives **exact GPS town coordinates* for all 463 tehsils in Pakistan while strictly preserving the administrative hierarchy:
- *Map Pin Coordinates*: Dropped at the specific tehsil centroid (e.g. Mian Channu = 30.3330N eval, vs Khanewal = 30.2934N, 72.0044E).
- *Administrative Fields*: adm2_name remains the parent district (e.g. Khanewal), adm1_name remains Punjab, and pcode remains PK615.
- *Zero Breaking Changes*: Filters, DDMA grouping, readback templates, and the public API contract remain 100% compatible.

---

## 2. Changes for Person A (Alisha) in `core/pipeline/geocode.py` -- SHIPPED, with a fix

**Status: done, but not with the 12-line snippet above.** That version's collision guard (`t_key != d_key`) only protects a tehsil from overwriting its OWN parent district -- it doesn't catch a tehsil colliding with a DIFFERENT district's name, or with another tehsil in a different district, or with an existing `aliases.json` entry pointing somewhere else. All three collisions are real in the actual 577-row gazetteer:

* **Different-district collision**: "Sahiwal" is both a real Punjab district AND, separately, an unrelated tehsil of Sargodha.
* **Cross-district tehsil collision**: "Khanpur" names a tehsil in three different provinces (Haripur/KP, Rahim Yar Khan/Punjab, Shikarpur/Sindh); "Kingri" in two (Khairpur, Musakhel).
* **Alias-table collision**: "naseerabad"/"nasir abad"/"dir" are all real tehsils whose names happen to equal an `aliases.json` entry hand-curated to mean a different district -- found via a full 1284-alias regression sweep, since this one only shows up when exact-match runs before alias lookup (see the addendum below).

The shipped `build_district_index(gazetteer, aliases)` checks all three before indexing a tehsil at admin-3 precision; an ambiguous name is skipped, not force-added, and falls back to its own (unambiguous) district-level entry instead. Full detail and verification: `docs/TRD.md` section 4.5's cascade-order addendum, `PROGRESS.md` CORE-18.

**Also fixed, same reasoning**: `_try_cascade()`'s stage order was alias-first; reordered to exact-first, since a literal match to a real district name is strictly more certain than a heuristic alias-table guess (this is what surfaced the "naseerabad"/"nasir abad"/"dir" collisions above -- they were already silently wrong before this reorder too, just via a different mechanism).

---

## 3. How to Activate Tehsil Target Aliases

**`tools/build_all_aliases.py` also needed the same collision guard** (`safe_set()`, added alongside the geocode.py fix) -- its original tehsil-loop and `URDU_MAP`/`TEHSIL_MAP` steps wrote directly into the aliases dict with no collision checking at all, and running it (in either mode) would have silently regenerated the exact "sahiwal"/"khanpur"/"kingri" ambiguities above. Verified: both `--tehsils` and default-mode output now correctly exclude all of them. One real, unavoidable disagreement worth knowing about: default-mode regeneration resolves "naseerabad" to Muzaffarabad (the tehsil's actual district) rather than the hand-curated "Nasirabad" (Balochistan) in the current `data/aliases.json` -- "Naseerabad" is a genuinely ambiguous Roman spelling shared by two different real places (a Balochistan district and an Azad Kashmir tehsil), and which one was intended is a judgment call, not a bug either way found this file's original author should weigh in on before regenerating.

Once ready, run:
```bash
python tools/build_all_aliases.py --tehsils
git commit -am "feat(geocode): activate tehsil-precision coordinates"
git push origin master
```

---

## 4. Render Cloud Auto-Deploy
Because Person A's change modifies `core/pipeline/geocode.py` inside `./core/`, Render's build trigger (`rootDir: ./core`) will automatically detect the commit and trigger an automatic rebuild and redeploy of `nidaa-core` to the live service.
