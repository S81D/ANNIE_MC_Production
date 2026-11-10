# GENIE stage

Generates BNB neutrino interactions in the ANNIE geometry with `gevgen_fnal`
([ANNIEsoft/GENIE-v3](https://github.com/ANNIEsoft/GENIE-v3)), one job per flux file.

**Inputs**
- Flux: `gsimple_flux_N.root` from `/pnfs/annie/persistent/users/jminock/flux/` (4000 files). Each is a random
  mix of 50 official ANNIE gsimple files, to avoid the "stripiness" of [DocDB 5586](https://annie-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid=5586).
- Cross sections: `gxspl-FNALsmall.xml`, read from LArSoft CVMFS
  (`genie_xsec v3_00_04_ub2`, md5 `fcce71a91d569aed4f405e8d52ae05c7`), so that ANNIE and MicroBooNE use the same
  splines for joint analyses.
- Geometry: `common/geometry/annie_v07.gdml`, the reduced world: dirt X [−7, +7], Y [−7.5, +6.5], Z [−10, +8] m.
- Tune `G18_10a_02_11a`, 20 000 events per job.

**GENIE build** (`genie.software`): `builtin` uses the genie3 image's GENIE. `tarball` runs your own build,
e.g. a fork; see `productions/example_custom_genie.yaml` and edit `worker/Setup_GENIE.sh` for its environment.

**Volume** (`genie.volume`): `world` (default) generates in the rock. The flux window is `ANNIE-rock`, and rays
start 10 m upstream (`-z -10`; this is the 2026-07-11 timing fix, without which vertex times are about 3 µs
instead of tens of ns). ⚠ `tank` is **untested**; anniedirt still runs afterwards. Use world generation.

**Worker** (`worker/genie_job.sh` → `genie_container.sh` → `run_annie_genie.sh`):
1. stage the flux file, geometry and scripts; copy the spline from CVMFS; unpack the tarball (`tarball` mode);
2. run `gevgen_fnal` (seed = run number in deterministic mode), then `gntpc` for the gst tree;
3. write the POT from the log to `pot_N.csv`; gzip the log.

`run_annie_genie.sh` is vendored from [S81D/GENIE-v3-O16](https://github.com/S81D/GENIE-v3-O16) (`annie/`); local
changes are marked `[mcprod]`.

**Outputs** (all always kept)

| File | Persistent dir |
|---|---|
| `gntp.N.ghep.root` | `genie/ghep` |
| `gntp.N.gst.root` | `genie/gst` |
| `pot_N.csv` (`run,POT`) | `genie/POT` |
| `gntp.N.ghep.log.gz`, `ANNIE-N.maxpl.xml`, `BNBFlux{N}.xml`, manifests | `genie/logs` |

`mcprod copy … genie` also writes `genie/POT_summary.txt` (POT summed over the runs present).
