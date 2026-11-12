# WCSim stage

Simulates the detector response to each run's GENIE + anniedirt events
([ANNIEsoft/WCSim](https://github.com/ANNIEsoft/WCSim), wcsim image). One job per run.

**Tarball** (`./mcprod tarball X.yaml wcsim`, from `wcsim.source_dir`, which contains `WCSim/`). Set it up first:
- `WCSim.mac`: `/mygen/generator beam`, and `/run/beamOn 20000` to read every event;
- `macros/primaries_directory.mac`: `/mygen/neutrinosdirectory ./gntp.*.ghep.root` and
  `/mygen/primariesdirectory ./annie_tank_flux.*.root`;
- `geniedirectory.txt`, `dirtdirectory.txt`: `./`;
- `build/sourceme`: added from `wcsim/sourceme` if missing.

**Worker** (`worker/wcsim_job.sh` → `wcsim_container.sh`):
1. unpack WCSim and move the GENIE + dirt files into `WCSim/build`;
2. append the seed to `macros/setRandomParameters.mac` (deterministic: run + 1), and copy the macros into the
   dummy file;
3. run `./WCSim WCSim.mac`; rename `wcsim_0.root` and `wcsim_lappd_0.root` to `_N`.

**Options**: `wcsim.outputs: both` (default) keeps the PMT and LAPPD files; `pmt` keeps the PMT file only.
`keep_logs` and `keep_failed_logs` are off by default.

**Outputs**

| File | Persistent dir |
|---|---|
| `wcsim_N.root` | `wcsim/pmts` |
| `wcsim_lappd_N.root` (about half the PMT size) | `wcsim/lappd` |
| `wcsim_N.log.gz` (if kept), manifests | `wcsim/logs` |
