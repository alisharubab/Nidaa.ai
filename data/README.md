# data/

| File | Status | Task |
| :-- | :-- | :-- |
| `pak_gazetteer.csv` | **Built.** 577 rows (one per admin-3 tehsil/sub-district), 160 districts, all 7 provinces/territories. Sourced from the official HDX COD-AB dataset (`pak_admin_boundaries.xlsx`, WFP SDI, [data.humdata.org/dataset/cod-ab-pak](https://data.humdata.org/dataset/cod-ab-pak)) — real P-codes and real centroid coordinates, zero missing values. Rebuild with `python tools/build_gazetteer.py path/to/pak_admin_boundaries.xlsx` if the source updates; the raw `.xlsx` isn't committed here, only this flattened output. | `DATA-01` ✅ |
| `aliases.json` | **Built.** 78 alias entries covering 43 real flood-prone districts (Sindh, Balochistan, South Punjab, KP), each verified to resolve to a district that actually exists in `pak_gazetteer.csv`. Canonical spellings come straight from the HDX data, which sometimes differs from common usage (e.g. `Kambar Shahdad Kot`, `D. I. Khan`, `Shaheed Benazir Abad`) — that's exactly the spelling drift this file exists to bridge. | `DATA-02` ✅ |
| `gold_set/` | Empty. Needs 25 hand-labelled messages (15 audio: 5 clean / 5 moderate / 5 severe, 10 text), each with a `label.json`. At least 8 of the 15 audio samples must be real human recordings, not synthetic TTS — see [../docs/TRD.md §8](../docs/TRD.md#8-test-harness). | `DATA-07` |

See [../docs/IMPLEMENTATION_PLAN.md](../docs/IMPLEMENTATION_PLAN.md) for full task context and [../PROGRESS.md](../PROGRESS.md) to check these off.
