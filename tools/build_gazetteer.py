"""DATA-01: builds data/pak_gazetteer.csv from the official HDX COD-AB
Pakistan administrative boundaries dataset (docs/TRD.md section 4.5).

Source: https://data.humdata.org/dataset/cod-ab-pak
Resource used: pak_admin_boundaries.xlsx (WFP SDI, P-coded, admin 0-3)
That file is NOT committed to this repo (raw source data, rebuildable) --
only the flattened data/pak_gazetteer.csv output is.

Usage:
    python tools/build_gazetteer.py path/to/pak_admin_boundaries.xlsx

Output columns match the TRD spec exactly:
    adm1_name,adm1_pcode,adm2_name,adm2_pcode,adm3_name,adm3_pcode,lat,lon

One row per admin-3 (tehsil/sub-district) area, using its own
center_lat/center_lon as the centroid -- the finest granularity the
source provides without parsing the shapefile geometry directly.
"""

import csv
import sys

import openpyxl

OUTPUT_COLUMNS = [
    "adm1_name", "adm1_pcode", "adm2_name", "adm2_pcode",
    "adm3_name", "adm3_pcode", "lat", "lon",
]


def build(xlsx_path: str, out_path: str) -> int:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb["pak_admin3"]
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    idx = {name: i for i, name in enumerate(header)}

    written = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)
        for row in rows:
            if row[idx["adm3_name"]] is None:
                continue
            writer.writerow([
                row[idx["adm1_name"]], row[idx["adm1_pcode"]],
                row[idx["adm2_name"]], row[idx["adm2_pcode"]],
                row[idx["adm3_name"]], row[idx["adm3_pcode"]],
                row[idx["center_lat"]], row[idx["center_lon"]],
            ])
            written += 1
    return written


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/build_gazetteer.py path/to/pak_admin_boundaries.xlsx")
        sys.exit(1)
    xlsx_path = sys.argv[1]
    out_path = "data/pak_gazetteer.csv"
    count = build(xlsx_path, out_path)
    print(f"Wrote {count} rows to {out_path}")


if __name__ == "__main__":
    main()
