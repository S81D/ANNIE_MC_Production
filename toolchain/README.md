# MC toolchain stage

Runs a ToolAnalysis toolchain over each run's WCSim + GENIE files (toolanalysis image), producing the analysis
ntuples. One job per run.

**Tarball** (`./mcprod tarball X.yaml toolchain`): `toolchain.source_dir/<ta_folder>`, without `.git`.
Re-tar after any ToolAnalysis change; the provenance file records the commit and whether the tree was dirty.

**Config hook** (`toolchain.config_hook`, default `hooks/config_GENIE.py`): copied into
`configfiles/<toolchain>/` and run with the run number. It writes the per-run `LoadWCSimConfig`
(`InputFile wcsim_N.root`) and `PhaseIITreeMakerConfig`, which are copied into the dummy file. Set it to `null` to
use the tarball's configs as they are.

**Worker** (`worker/toolchain_job.sh` → `toolchain_container.sh`): unpack ToolAnalysis, move in
`wcsim_N.root` + `gntp.N.ghep.root` (+ `wcsim_lappd_N.root` with `attach_lappd: true`), run the hook,
`source Setup.sh`, `./Analyse configfiles/<toolchain>/ToolChainConfig`, then rename `output_file` to `MC_N.root`.

**Logs** are off by default (the GENIE-reweight output is tens of MB per job). `keep_failed_logs: true` returns
them for failed jobs only.

**Before copying**: run `mcprod verify`, then `purge`. The check needs `phaseIITriggerTree`,
`phaseIITankClusterTree` and `phaseIIMRDClusterTree` (`toolchain.verify_trees`). Toolchains that don't fill a
tree, or the newer single-tree output, need a different list. `verify` stops if a tree is missing even from the
largest files.

Known: PMTWaveformSim uses `new TRandom3()`, which is ROOT's fixed seed 4357, so every job draws the same waveform
sequence. Fixing that needs a ToolAnalysis change.

**Outputs**

| File | Persistent dir |
|---|---|
| `MC_N.root` | `MC_toolchain/<version>` |
| `toolchain_N.log.gz` (if kept), manifests | `MC_toolchain/<version>/logs` |

`mcprod copy … toolchain` also writes `MC_toolchain/<version>/POT_summary.txt`.
