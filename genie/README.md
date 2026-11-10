# GENIE and ANNIEDirt Production
ANNIE's official GENIE repository (https://github.com/ANNIEsoft/GENIE-v3) and the corresponding Geant4 dirt simulation that propagates final state particles to the active detector (https://github.com/ANNIEsoft/anniedirt). This workflow is optimized for event generation within the ANNIE world volume (`WORLD_LV`), but can be modified for tank-only generation.

---

## Overview (powered by Claude AI)

This repository provides grid submission scripts for running GENIE neutrino interaction simulations for the ANNIE experiment (`genie/`) and for running anniedirt (`anniedirt/`) - the machinery to propagate final state (FS) particles from their interaction to the active detector volume. Both of these steps are required for an end-to-end simulation pipeline which includes WCSim and ToolAnalysis.

Jobs are submitted to the Fermilab grid via `jobsub_submit` and run inside the `anniesoft/genie3` and `anniesoft/anniedirt` Singularity containers. GENIE uses BNB gsimple flux files, while anniedirt uses the corresponding gntp.ghep.root files produced from GENIE. Both also use a `annie_v*.gdml` detector geometry. The GENIE scripts support running from either the official container-bundled GENIE installation or a local fork packaged as a tar archive; anniedirt scripts currently only support from running the official container-bundled installation.

---

## `genie/`

| Script | Role |
|---|---|
| `submit_GENIE_jobs.sh` | Entry point — configure and submit batch jobs to the grid |
| `GENIE_grid.sh` | Worker node script — copies inputs, extracts GENIE tar, launches Singularity |
| `rub_the_lamp.sh` | Runs inside the Singularity container — sources the GENIE environment and calls `run_annie_genie.sh` |
| `run_annie_genie.sh` | Calls `gevgen_fnal`, handles geometry, flux window, fiducial cuts, and output |
| `Setup_GENIE.sh` | Configures environment variables for a local fork of GENIE (only sourced when `USE_LOCAL_GENIE=true`) |
| `tar_GENIE.py` | Tar generation script for local GENIE fork |
| `missing_ghep.py` | Displays a missing file report following grid submission, telling the user which files need to be re-submitted and which are ready for transfer. |
| `copy_genie_output.sh` | Transfer script to copy grid output files from `scratch/` to a more persistent location. |

All scripts except `submit_GENIE_jobs.sh` live in a `lib/` subdirectory of your pnfs input folder (see below).

---

## Prerequisites

- Access to the BNB gsimple flux files at `/pnfs/annie/persistent/users/jminock/flux/`
- An annie geometry file - the "default" geometry file can be found [here (annie_v04.gdml)](https://github.com/ANNIEsoft/GENIE-v3/tree/master/annie). A copy of a reduced geometry to boost efficiency for world event generation is given in `lib/annie_v07.gdml`
- The `gxspl-FNALsmall.xml` cross-section spline file (too large for this repository — place it manually in `lib/`)

---

## Input Directory Layout

The `INPUT_FOLDER` defined in `submit_GENIE_jobs.sh` must be organised as follows:

```
INPUT_FOLDER/
├── GENIE.tar.gz          # local GENIE fork (only if USE_LOCAL_GENIE=true)
├── submit_GENIE_jobs.sh
└── lib/
    ├── GENIE_grid.sh
    ├── copy_genie_output.sh
    ├── missing_ghep.py
    ├── rub_the_lamp.sh
    ├── run_annie_genie.sh
    ├── Setup_GENIE.sh    # only needed if USE_LOCAL_GENIE=true
    ├── annie_v*.gdml
    └── gxspl-FNALsmall.xml
```

> **Note:** `gxspl-FNALsmall.xml` is not included in this repository due to its size (~460 MB). Obtain it from the GENIE data releases or a collaborator and place it in `lib/` before submitting. The cross section file can be found here through LArSoft: `/cvmfs/larsoft.opensciencegrid.org/products/genie_xsec/v3_00_04_ub2/NULL/G1810a0211a-k250-e1000/data/gxspl-FNALsmall.xml` - this specific file is used as to allow for joint analysis with MicroBooNE and is the default file used for ANNIE analyses.

### Preparing a local GENIE tar archive

If using a local fork (`USE_LOCAL_GENIE=true`), edit the following script to reflect your workflow and then package your compiled GENIE installation from the Fermilab GPVMs:

```python
python3 lib/tar_GENIE.py
```

The folder name inside the archive must match `GENIE_FOLDER_NAME` in `submit_GENIE_jobs.sh`. Place the resulting `.tar.gz` directly in `INPUT_FOLDER` (not in `lib/`).

---

## Configuration

All user-facing settings are in the `INPUTS` block at the top of `submit_GENIE_jobs.sh`:

```bash
GRID_USER=doran             # please change to reflect your username
INPUT_FOLDER=/pnfs/annie/scratch/users/${GRID_USER}/grid_wcsim/GENIE_G4Dirt_production/
OUTPUT_FOLDER=/pnfs/annie/scratch/users/${GRID_USER}/output/

USE_LOCAL_GENIE=true        # true = use tar archive; false = use container's built-in GENIE
GENIE_TAR_NAME=GENIE.tar.gz
GENIE_FOLDER_NAME=GENIE-v3-O16

RUNS=$(seq 0 1)             # consecutive (default)
#RUNS="435 2282"            # specific re-processing

LIFETIME=4                  # job lifetime in hours
DISK_SPACE=10               # GB per job
MEMORY_SPACE=4000           # MB per job
ONSITE_JOB=true             # true = FNAL/onsite; false = offsite (with site blacklist)
```

Each run number maps to a corresponding flux file `gsimple_flux_${RUN}.root` in the flux folder and produces an independent output file. To resubmit specific runs (for example, if they fail), you can uncomment the second line.

---

## Running

```bash
chmod +x submit_GENIE_jobs.sh
source submit_GENIE_jobs.sh
```

The script performs a pre-flight check to verify all required input files are present before submitting. Jobs that already have output in `OUTPUT_FOLDER` are automatically skipped.

### What happens on the worker node

1. `GENIE_grid.sh` copies all input files from `CONDOR_DIR_INPUT` to the job's `/srv` working area.
2. If using a local fork, the GENIE tar archive is extracted into `/srv`.
3. The `anniesoft/genie3` Singularity container is launched with `/srv` bind-mounted.
4. Inside the container, `rub_the_lamp.sh` sources `Setup_GENIE.sh` (local fork) or the container's built-in setup, then calls `run_annie_genie.sh`.
5. `run_annie_genie.sh` executes `gevgen_fnal` with the BNB flux, `annie_v*.gdml` geometry, the `G18_10a_02_11a` tune, and `WORLD_LV` as the top volume, generating 20,000 events.
6. The GHEP output is converted to a flat GST tree via `gntpc`.
7. The POT normalization is scraped from the log and written to a per-run CSV.
8. The log file is compressed with `gzip -9`.
9. All outputs are copied to `OUTPUT_FOLDER` via `ifdh`.

---

## Output Files

For each run `N`, the following files are written to `OUTPUT_FOLDER`:

| File | Description |
|---|---|
| `gntp.N.ghep.root` | Full GENIE GHEP event record |
| `gntp.N.gst.root` | Flat GST summary tree (produced by `gntpc`) |
| `gntp.N.ghep.log.gz` | Compressed `gevgen_fnal` log (flux scanning, event printout, normalization) |
| `pot_N.csv` | Two-column single-line CSV: `run,POT` (e.g. `3,1.10656e+17`) |
| `BNBFlux_N.xml` | BNB flux driver configuration used for this run |
| `ANNIE-N.maxpl.xml` | Maximum path-length file generated during the run |
| `N_<jobid>_dummy_output` | Job metadata log (timing, arguments, file listings) |

### Collecting POT across all runs

After all jobs complete, aggregate the per-run CSV files via:

```bash
echo "run,pot" > pot_summary.csv
cat pot_*.csv >> pot_summary.csv
```

You can also run a post-job report using `python3 missing_ghep.py <scratch_path> <run_start> <run_end>` for information on which jobs are complete and which should be re-submitted (failed). To initiate the copying of files from `scratch/` to a more persistent location, run `./copy_genie_output.sh <scratch_path> <persistent_path>`.

### Up to date flux files for ANNIE

The most up to date flux files live in James Minock's area: `/pnfs/annie/persistent/users/jminock/flux/`

These files were produced to generate the default, existing GENIE samples. Each file is a random combination of 50 official ANNIE gsimple flux files to avoid the "stripiness" issues described in [ANNIE Document 5586-v1](https://annie-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid=5586)

---

## `anniedirt/`

The anniedirt scripts follow the same conventions as the `genie/` scripts above — refer to those sections for further detail.

| Script | Role |
|---|---|
| `submit_anniedirt_jobs.sh` | Entry point — configure and submit batch jobs to the grid |
| `g4dirt_grid.sh` | Worker node script — copies inputs, extracts GDML schemas, launches Singularity |
| `run_g4dirt_container.sh` | Runs inside the Singularity container — calls `run_g4dirt.sh` and compresses the log |
| `missing_dirt.py` | Displays a missing file report following grid submission, telling the user which files need to be re-submitted and which are ready for transfer. |
| `copy_dirt_output.sh` | Transfer script to copy grid output files from `scratch/` to a more persistent location. |

All scripts except `submit_anniedirt_jobs.sh` live in a `lib/` subdirectory of your pnfs input folder:

```
INPUT_FOLDER/
├── submit_GENIE_jobs.sh
└── lib/
    ├── g4dirt_grid.sh
    ├── run_g4dirt_container.sh
    ├── copy_dirt_output.sh
    ├── missing_dirt.py
    ├── annie_v*.gdml
    └── gdml.tar.gz
```

> **Note:** `gdml.tar.gz` is a tar archive of the GDML XML schema files (`.xsd`) that Geant4 requires to parse the geometry at runtime. It is not produced by this repository — obtain it from a collaborator or from an existing ANNIEDirt installation and place it in `lib/` before submitting (it's provided in the `lib/` folder within this directory).

Unlike the GENIE scripts, anniedirt runs exclusively through the official `anniesoft/g4dirt:latest` Singularity container. There is no local-fork support currently (TODO).

---

### Configuration

All user-facing settings are in the `INPUTS` block at the top of `submit_anniedirt_jobs.sh`:

```bash
GRID_USER=doran             # change to reflect your username
INPUT_FOLDER=/pnfs/annie/scratch/users/${GRID_USER}/grid_wcsim/GENIE_G4Dirt_production/anniedirt/
OUTPUT_FOLDER=/pnfs/annie/scratch/users/${GRID_USER}/output/G4Dirt_production/

GENIE_PATH=/pnfs/annie/persistent/users/${GRID_USER}/GENIE/  # path to gntp.*.ghep.root files

RUNS=$(seq 0 1)     # consecutive (default)
#RUNS="435 2282"    # specific re-processing

LIFETIME=4          # hr
DISK_SPACE=10       # GB
MEMORY_SPACE=4000   # MB
ONSITE_JOB=true
```

`GENIE_PATH` must point to the directory containing the `gntp.${RUN}.ghep.root` files produced by the GENIE workflow. Run numbers are matched one-to-one: ANNIEDirt run `N` consumes `gntp.N.ghep.root` and produces `annie_tank_flux.N.root`. Jobs whose output already exists in `OUTPUT_FOLDER` are automatically skipped.

---

### Running

```bash
chmod +x submit_anniedirt_jobs.sh
source submit_anniedirt_jobs.sh
```

### What happens on the worker node

1. `g4dirt_grid.sh` copies `gntp.${RUN}.ghep.root`, `annie_v07.gdml`, and `gdml.tar.gz` from `CONDOR_DIR_INPUT` to `/srv`.
2. The GDML schema archive is extracted in-place and removed.
3. The `anniesoft/g4dirt:latest` Singularity container is launched with `/srv` bind-mounted.
4. Inside the container, `run_g4dirt_container.sh` sources `/home/run_g4dirt.sh`, running ANNIEDirt over the GENIE events with the specified geometry.
5. The output log is compressed with `gzip -9`.
6. Outputs are copied to `OUTPUT_FOLDER` via `ifdh` and `/srv` is cleaned up.

You can run a post-job report using `python3 missing_dirt.py <scratch_path> <run_start> <run_end>` for information on which jobs are complete and which should be re-submitted (failed). To initiate the copying of files from `scratch/` to a more persistent location, run `./copy_dirt_output.sh <scratch_path> <persistent_path>`.

---

### Output Files

For each run `N`, the following files are written to `OUTPUT_FOLDER`:

| File | Description |
|---|---|
| `annie_tank_flux.N.root` | ANNIEDirt output — FS particles propagated to the tank volume |
| `annie_tank_flux.N.log.gz` | Compressed ANNIEDirt log |
| `N_<jobid>_dummy_output` | Job metadata log (timing, arguments, file listings) |

---

## Troubleshooting

**Un-zipping log files**
`gunzip *.log.gz*`, which will leave you with a corresponding `*.log` file.

**Missing input file at submission**
The pre-flight check in `submit_GENIE_jobs.sh` will print the missing path and exit before any jobs are submitted.

**Resubmitting failed runs**
Any run whose output file already exists in `OUTPUT_FOLDER` is automatically skipped. For selective resubmission use the `redoruns` array pattern shown in the Configuration section above.

