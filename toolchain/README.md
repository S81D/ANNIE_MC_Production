# MC toolchain stage

Runs a ToolAnalysis toolchain over each run's WCSim + GENIE files (toolanalysis image), producing the analysis
ntuples. One job per run.

**Tarball** (`./mcprod tarball X.yaml toolchain`): `toolchain.source_dir/<ta_folder>`, without `.git`.
Re-tar after any ToolAnalysis change; the provenance file records the commit and whether the tree was dirty.

## ⚠ Edit the tree-maker config script before you run

Every job runs a small Python script with the run number, inside `configfiles/<toolchain>/`. It writes the per-run
`LoadWCSimConfig` (`InputFile wcsim_N.root`, channel maps) and the `PhaseIITreeMakerConfig`: the settings of the
PhaseIITreeMaker tool, i.e. what goes into your ntuple. Two versions are provided:

| Script | Analysis | PhaseIITreeMaker lines that differ |
|---|---|---|
| `hooks/config_GENIE.py` (default) | CC | `MRDRecoSource Both`, `SimpleReco_fill 1`, `TankReco_fill 1`, `RecoDebug_fill 1`, `PMTWaveformSim 0`, `VertexLeastSquares 0` |
| `hooks/config_GENIE_NC.py` | NC | no `MRDRecoSource` or `SimpleReco_fill` line, `TankReco_fill 0`, `RecoDebug_fill 0`, `PMTWaveformSim 1`, `VertexLeastSquares 1` |

**Edit the one you use to reflect your workflow, and commit it.** It is copied into your tarball's
`configfiles/<toolchain>/`, replacing any `config_GENIE.py` there. Its settings must match the tools in that
toolchain's `ToolsConfig`, and its `OutputFile` must equal `toolchain.output_file` (default `tree.root`).
Choose the script with `toolchain.config_hook`.

To disable this and run the `config_GENIE.py` already in your tarball's toolchain folder, set
`config_hook: tarball`. Either way the dummy file records which script ran, its md5, whether it matches the
tarball's copy, and the `LoadWCSimConfig` and `PhaseIITreeMakerConfig` it wrote. A job whose script is missing or
fails stops before `Analyse`.

**Worker** (`worker/toolchain_job.sh` → `toolchain_container.sh`): unpack ToolAnalysis, move in
`wcsim_N.root` + `gntp.N.ghep.root` (+ `wcsim_lappd_N.root` with `attach_lappd: true`), run the config script,
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
