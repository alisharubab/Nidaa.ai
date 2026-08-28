# data/

| File | Status | Task |
| :-- | :-- | :-- |
| `pak_gazetteer.csv` | **Not yet built.** Download Pakistan COD-AB admin 0-3 tables from [HDX](https://data.humdata.org/dataset/cod-ab-pak) and flatten per the column spec in [../docs/TRD.md §4.5](../docs/TRD.md#45-stage-3-geocoding-geocodepy). | `DATA-01` |
| `aliases.json` | Seeded with the 5 example districts from the TRD. Needs expansion to the top 40 flood-affected districts. | `DATA-02` / `DATA-04` |
| `gold_set/` | Empty. Needs 25 hand-labelled messages (15 audio: 5 clean / 5 moderate / 5 severe, 10 text), each with a `label.json`. At least 8 of the 15 audio samples must be real human recordings, not synthetic TTS — see [../docs/TRD.md §8](../docs/TRD.md#8-test-harness). | `DATA-07` |

See [../docs/IMPLEMENTATION_PLAN.md](../docs/IMPLEMENTATION_PLAN.md) for full task context and [../PROGRESS.md](../PROGRESS.md) to check these off.
