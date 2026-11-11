# Configuration reference

One YAML per production (`productions/*.yaml`). Only `production.name` and `runs` are required; every other key
has the default below (`common/mcprod_lib/config.py`). Unknown keys are errors. Placeholders: `{user}`,
`{production}`, and `{version}` (toolchain version, in `layout`). Write keys containing placeholders in block
style, or quote them; `{...}` is YAML's mapping syntax.

| Key | Default | Meaning |
|---|---|---|
| `production.name` | — | used in every path and record |
| `production.user` | `$USER` | grid user |
| `production.group` | `annie` | jobsub group |
| `runs.range` / `runs.list` | — | `[first, last]` inclusive, or an explicit list |
| `seeds.mode` | `deterministic` | or `random` (docs/workflow.md) |
| `grid.site` | `onsite` | `onsite` = `DEDICATED,OPPORTUNISTIC`; `offsite` = `OFFSITE` + blacklist |
| `grid.offsite_blacklist` | Omaha, Swan, Wisconsin, SU-ITS, RAL | offsite only |
| `grid.auto_release`, `grid.grace_memory` | `true`, `4000MB` | `+FERMIHTC_AutoRelease`, `+FERMIHTC_GraceMemory` (memory only) |
| `grid.confirm_above` | `10` | ask before submitting more jobs than this |
| `recovery.complete_fraction` | `0.95` | stage counts as complete |
| `test.n_jobs`, `test.runs` | `10`, first runs | the test campaign |
| `test.margins`, `test.memory_step` | 1.25 / 1.5 / 2.0, `2000MB` | `estimate`: memory, disk, walltime factors |
| `paths.scratch` | `/pnfs/annie/scratch/users/{user}/ANNIE_MC_Production/{production}` | grid output (`<stage>/`, `test/<stage>/`) |
| `paths.persistent` | `/pnfs/annie/persistent/users/{user}/{production}` | final samples (see `layout`) |
| `paths.flux_dir` | `/pnfs/annie/persistent/users/jminock/flux` | `gsimple_flux_N.root` |
| `paths.geometry` | `common/geometry/annie_v07.gdml` | GENIE + anniedirt geometry |
| `paths.container_tmp` | `/exp/annie/app/users/{user}/temp_directory` | `/tmp` for `verify`/`validate` |
| `validation.reference_dir` | `/pnfs/annie/persistent/users/doran/PRODUCTION_MC_VALIDATION_FILES` | reference files |
| `layout.<stage>.*` | `genie/{ghep,gst,logs,POT}`, `anniedirt/{annie,logs}`, `wcsim/{pmts,lappd,logs}`, `MC_toolchain/{version}` | persistent sub-directories |
| `transfer.method`, `batch_size` | `ifdh`, `100` | `cp` is the fallback if ifdh fails |
| `<stage>.container` | `/cvmfs/singularity.opensciencegrid.org/anniesoft/{genie3,g4dirt,wcsim,toolanalysis}:latest` | image |
| `<stage>.resources` | 4000MB, 10GB (genie/anniedirt) or 5GB, 4h | memory, disk, lifetime |
| `<stage>.verify_trees` | `gtree` · `tankflux tankmeta` · `wcsimT wcsimGeoT` · `phaseIITriggerTree phaseIITankClusterTree phaseIIMRDClusterTree` | `verify` |
| `genie.software` | `builtin` | or `tarball` (+ `tarball`, `tarball_folder`, `source_dir`, `setup_script`) |
| `genie.spline` | LArSoft `genie_xsec v3_00_04_ub2` `gxspl-FNALsmall.xml` | read from CVMFS |
| `genie.tune`, `events_per_job` | `G18_10a_02_11a`, `20000` | |
| `genie.volume`, `tank_topvol` | `world`, `TWATER_LV` | tank is untested |
| `genie.flux_file`, `flux_index_offset` | `gsimple_flux_{index}.root`, `0` | flux index = run − offset |
| `anniedirt.input` | persistent `genie/ghep` | GENIE files to read |
| `anniedirt.events_per_job` | `20000` | |
| `wcsim.tarball`, `source_dir` | — | tarball path on pnfs; folder containing `WCSim/` |
| `wcsim.genie_input`, `dirt_input` | persistent genie / anniedirt | e.g. an official sample |
| `wcsim.outputs` | `both` | or `pmt` |
| `<wcsim/toolchain>.keep_logs`, `keep_failed_logs` | `false`, `false` | return logs (always on in test mode) |
| `toolchain.tarball`, `source_dir`, `ta_folder`, `toolchain` | — | ToolAnalysis tarball and toolchain name |
| `toolchain.version` | `v1.0` | output folder `MC_toolchain/<version>` |
| `toolchain.config_hook` | `toolchain/hooks/config_GENIE.py` | per-run config script, copied into the tarball (CC; NC: `toolchain/hooks/config_GENIE_NC.py`), or `tarball` to run the tarball's own `configfiles/<toolchain>/config_GENIE.py` |
| `toolchain.output_file` | `tree.root` | renamed `MC_N.root` |
| `toolchain.attach_lappd` | `false` | also give the job `wcsim_lappd_N.root` |
| `toolchain.wcsim_input`, `lappd_input`, `genie_input`, `pot_input` | persistent defaults | overrides |
