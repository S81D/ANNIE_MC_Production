# Legacy MC-tuning workflows (frozen)

Kept for reference, unchanged: they are not part of the production chain, are not maintained, and contain
hard-coded paths and users. The repository as it was before the restructuring is tagged `pre-refactor`.

| Folder | Was used for |
|---|---|
| `AmBe_neutrons/` | AmBe-like neutrons in WCSim at the 2024 calibration ports (1, 5, 4, 3), depths −100…100 cm; spectrum in `AmBe_spectrum.dat` (from RATPAC) |
| `dirt_muons/` | Michel electrons via their parent dirt muons (`dirt_muons_genie.txt`); only about 0.5 % yield a Michel candidate, so about 500k events are needed; `MC_toolchain_dirt_muons/` batches the WCSim files through a toolchain |
| `genie_muons/` | through-going muons (FMV + tank + MRD) from `thru_genie_muons.txt`, for CC tuning |
| `submit_MC_toolchain/` | toolchain jobs over batches of the muon WCSim files |
