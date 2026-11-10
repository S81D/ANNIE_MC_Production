# grid_wcsim
Submitting WCSim grid jobs for GENIE samples. Currently designed for WORLD samples (1 GENIE + 1 Flux file per job).

## Details and Usage

- For `WCSim.mac`, please enable: `/mygen/generator beam` for the event action.
- The GENIE sanples contain 20k events - set `/run/beamOn 20000` to run over all events. Note that the WORLD GENIE samples will only contain ~600 events per file due to most events never having a FS particle make it to the detector to simulate in WCSim. For the tank samples, it is more complicated due to the observed "stripiness".
- In `primaries_directory.mac`, specify a local path for the GENIE + flux files:

```
/mygen/neutrinosdirectory ./gntp.*.ghep.root
/mygen/primariesdirectory ./annie_tank_flux.*.root
```

- In `geniedirectory.txt` and `dirtdirectory.txt`, set the upstream directory path to: `./` (since you're running over files within the pwd on the grid node).
- See the global `README` for more details.
