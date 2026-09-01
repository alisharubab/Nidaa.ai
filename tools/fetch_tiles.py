"""FE-10: offline OSM tile cache for the demo bounding box.

Downloads zoom 6-9 OpenStreetMap raster tiles covering Sindh / South
Punjab into dashboard/tiles/{z}/{x}/{y}.png so the pitch demo map renders
with no internet (REL-03 airplane-mode rehearsal, DoD item 10).

Usage (from repo root):
    python tools/fetch_tiles.py            # download missing tiles
    python tools/fetch_tiles.py --dry-run  # just count

Re-runs are idempotent: existing files are skipped, so partial downloads
(CTRL+C, flaky wifi) can simply be resumed. Keep the volume modest and
the delay in place -- OSM's tile usage policy asks bulk fetchers to be
gentle; ~150 tiles once is well within it.
"""

import argparse
import math
import sys
import time
import urllib.request
from pathlib import Path

# Bounding box: Sindh + South Punjab (Dadu/Larkana/Sukkur belt through
# Multan/Bahawalpur division). Covers the default map view (center 26.5N
# 68.0E, zoom 7) with comfortable pan headroom on all sides.
LAT_MIN, LAT_MAX = 23.5, 31.5
LON_MIN, LON_MAX = 66.5, 74.0
ZOOMS = (6, 7, 8, 9)

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OUT_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "tiles"

# OSM tile policy: identify the app, don't pretend to be a browser.
HEADERS = {"User-Agent": "NidaaAI-demo-tile-cache/1.0 (hackathon demo; contact: repo owners)"}

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def deg2tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Slippy map tile numbers for a lat/lon at a zoom level."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tiles_for_bbox() -> list[tuple[int, int, int]]:
    tiles: list[tuple[int, int, int]] = []
    for z in ZOOMS:
        # NW corner (north -> smallest y, west -> smallest x) and SE corner
        # give the inclusive tile range for the bbox.
        x_min, y_min = deg2tile(LAT_MAX, LON_MIN, z)
        x_max, y_max = deg2tile(LAT_MIN, LON_MAX, z)
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tiles.append((z, x, y))
    return tiles


def fetch(z: int, x: int, y: int, dest: Path) -> tuple[bool, str]:
    url = TILE_URL.format(z=z, x=x, y=y)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as res:
            data = res.read()
    except Exception as exc:  # noqa: BLE001 - report and continue
        return False, str(exc)
    if not data.startswith(PNG_MAGIC):
        return False, "not a PNG (likely an error page)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True, f"{len(data)} bytes"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="count only, download nothing")
    args = parser.parse_args()

    tiles = tiles_for_bbox()
    per_zoom: dict[int, int] = {}
    for z, _, _ in tiles:
        per_zoom[z] = per_zoom.get(z, 0) + 1
    print(f"bbox lat {LAT_MIN}-{LAT_MAX}, lon {LON_MIN}-{LON_MAX}")
    for z in ZOOMS:
        print(f"  zoom {z}: {per_zoom.get(z, 0)} tiles")
    print(f"  total: {len(tiles)} tiles -> {OUT_DIR}")

    if args.dry_run:
        return 0

    ok = skip = fail = 0
    for i, (z, x, y) in enumerate(tiles, 1):
        dest = OUT_DIR / str(z) / str(x) / f"{y}.png"
        if dest.exists() and dest.stat().st_size > 0:
            skip += 1
            continue
        success, detail = fetch(z, x, y, dest)
        if success:
            ok += 1
        else:
            fail += 1
            print(f"  FAIL z{z}/{x}/{y}: {detail}")
        if i % 25 == 0:
            print(f"  ... {i}/{len(tiles)} (ok {ok}, skip {skip}, fail {fail})")
        time.sleep(0.15)  # be polite to the tile servers

    print(f"done: {ok} downloaded, {skip} already present, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
