# ANNIE MC Production

Grid production of ANNIE simulation samples on FermiGrid: **GENIE → anniedirt → WCSim → MC toolchain**.
One YAML file describes a production; one command, `./mcprod`, submits, tracks, recovers, validates and
transfers each stage.

```
gsimple_flux_N ─GENIE─▶ gntp.N.ghep.root ─anniedirt─▶ annie_tank_flux.N.root ─WCSim─▶ wcsim_N.root (+ wcsim_lappd_N.root) ─toolchain─▶ MC_N.root
```

## ⚠ Disk impact — read before running a production

A full production (4000 runs) is large, and dCache space is shared by all of ANNIE. Measured with `du -sh`:

| Stage | Size |
|---|---|
| GENIE (ghep + gst + logs) | ~100 GB |
| anniedirt | ~2 GB |
| WCSim, PMT files only | ~115 GB |
| WCSim, PMT + LAPPD files (default) | ~170 GB |
| MC toolchain (with GENIE + flux weights) | ~120 GB |
| **Full chain** | **~0.4 TB**, plus a scratch copy until transfer |

Run the 10-job test chain first, transfer promptly, and coordinate with the collaboration before a full production.

## Quick start (ANNIE gpvm)

```
kinit $USER@FNAL.GOV
htgettoken -a htvaultprod.fnal.gov -i annie
git clone https://github.com/S81D/ANNIE_MC_Production.git /exp/annie/app/users/$USER/ANNIE_MC_Production
cd /exp/annie/app/users/$USER/ANNIE_MC_Production
cp productions/example_world.yaml productions/my_sample.yaml
./mcprod check productions/my_sample.yaml
```

Edit `productions/my_sample.yaml` (name, runs, WCSim and ToolAnalysis sources) before `check`.

**MC toolchain users:** the toolchain stage sets up the tree maker (PhaseIITreeMaker) with a Python config script
that is copied into your ToolAnalysis tarball and run in every job. Two versions are provided:
`toolchain/hooks/config_GENIE.py` (CC, the default) and `toolchain/hooks/config_GENIE_NC.py` (NC). Edit the one you
use to reflect your workflow, or set `toolchain.config_hook: tarball` to run the `config_GENIE.py` inside your
tarball's toolchain folder instead. Details: [toolchain/README.md](toolchain/README.md).

Then follow
[docs/workflow.md](docs/workflow.md): test every stage, then run the full production stage by stage.
**Launch a stage — test or full — only when the previous stage is DONE.** `mcprod` enforces this.

## Commands

| Command | Does |
|---|---|
| `./mcprod check X.yaml` | validate the config, inputs, images, spline, auth |
| `./mcprod tarball X.yaml wcsim\|toolchain\|genie` | build the software tarball (+ provenance file) |
| `./mcprod submit X.yaml STAGE [--test] [--dry-run] [--missing]` | submit jobs (`--missing` = recovery campaign) |
| `./mcprod status X.yaml STAGE [--test]` | completeness, campaign history, failures, queue |
| `./mcprod validate X.yaml STAGE` | test jobs vs reference files: GREEN / YELLOW / RED |
| `./mcprod estimate X.yaml STAGE` | memory / disk / walltime requests from the test jobs |
| `./mcprod verify X.yaml STAGE` · `purge` | find (and delete, with confirmation) broken scratch files |
| `./mcprod copy X.yaml STAGE` | scratch → persistent, size-verified; writes the POT summary |
| `./mcprod pot X.yaml genie\|toolchain` | POT summary on its own |

Long steps (submitting or copying ~4000 files) take hours: run them in `screen` (docs/workflow.md).

## Layout

| Path | Contents |
|---|---|
| `productions/` | one YAML per production (commit yours: it is the record of what was run) |
| `genie/ anniedirt/ wcsim/ toolchain/` | stage README + worker scripts |
| `common/` | geometry (`annie_v07.gdml`), shared worker functions, `mcprod` library |
| `helpers/` | broken-file finder/deleter, POT summer, POT from ghep files |
| `validation/` | `validate.py` (used by `mcprod validate`) |
| `docs/` | workflow, configuration reference, troubleshooting |
| `tests/` | `python3 -m unittest discover tests` (no grid needed) |
| `legacy/` | frozen MC-tuning workflows (AmBe, Michel, through-going muons) |
| `records/` | local bookkeeping written by `mcprod` (not in git) |

Requirements: an ANNIE gpvm (jobsub_lite, singularity, system `python3` with PyYAML) and an ANNIE grid account.

## AI assistance

The grid scripts for every stage were written and used for ANNIE MC production before any AI assistance.
AI (Claude, Anthropic) was used, under Steven Doran's direction and review, to compress and streamline them
into one configuration-driven workflow, with shared worker code, tests and documentation. Physics settings
(GENIE tune, flux, geometry, events per job) were not changed. The pre-AI version is tagged `pre-refactor`.
