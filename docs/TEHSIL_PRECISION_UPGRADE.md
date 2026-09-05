# Tehsil-Level (Admin-3) Coordinate Precision Upgrade

## 1. Overview
In the initial MVP, all tickets within a district shared the district centroid coordinates. For large districts (e.g. Khanewal, Dadu, Sukkur, Lasbela, Rajanpur), towns and tehsils located 40-80 km apart stacked on the exact same map coordinates.

This upgrade gives **exact GPS town coordinates* for all 463 tehsils in Pakistan while strictly preserving the administrative hierarchy:
- *Map Pin Coordinates*: Dropped at the specific tehsil centroid (e.g. Mian Channu = 30.3330N eval, vs Khanewal = 30.2934N, 72.0044E).
- *Administrative Fields*: adm2_name remains the parent district (e.g. Khanewal), adm1_name remains Punjab, and pcode remains PK615.
- *Zero Breaking Changes*: Filters, DDMA grouping, readback templates, and the public API contract remain 100% compatible.

---

## 2. Changes for Person A (Alisha) in `core/pipeline/geocode.py`

In `build_district_index(gazetteer) -> dict`, add the following 12 lines right after the district grouping loop:

```python
    # Sub-district / Tehsil-level precision: index individual tehsils so pins drop
    # at the town's exact coordinates while keeping the parent district tagged!
    for row in gazetteer:
        t_key = _normalize(row["adm3_name"])
        d_key = _normalize(row["adm2_name"])
        if t_key and t_key != d_key:
            index[t_key] = {
                "adm2_name": row["adm2_name"],
                "adm1_name": row["adm1_name"],
                "pcode": row["adm2_pcode"],
                "latitude": float(row["lat"]),
                "longitude": float(row["lon"]),
            }
```

---

## 3. How to Activate Tehsil Target Aliases

Once Person A commits the above change to `core/pipeline/geocode.py`, run:
```bash
python tools/build_all_aliases.py --tehsils
git commit -am "feat(geocode): activate tehsil-precision coordinates"
git push origin master
```

---

## 4. Render Cloud Auto-Deploy
Because Person A's change modifies `core/pipeline/geocode.py` inside `./core/`, Render's build trigger (`rootDir: ./core`) will automatically detect the commit and trigger an automatic rebuild and redeploy of `nidaa-core` to the live service.
