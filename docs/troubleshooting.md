# Troubleshooting

**Held jobs**: memory overruns are released automatically with +4 GB (`FERMIHTC_AutoRelease`); disk and walltime
are not. Inspect and clear:
```
jobsub_q -G annie --user $USER -af JobsubJobId HoldReason
jobsub_rm -G annie --constraint 'JobStatus==5 && Owner=="'$USER'"'
```
Then raise the stage's `resources` and run `submit --missing`.

**Usage of a running or finished job**: `jobsub_q -G annie --user $USER -af JobsubJobId ResidentSetSize_RAW
MemoryUsage DiskUsage_RAW RequestDisk`. Don't use plain `DiskUsage`, which is rounded up.

**A failed run**: its dummy file (`<run>_<jobid>_dummy_output` in the scratch output dir) has the arguments,
inputs, seed, container, peak memory and disk, and `MCPROD_STATUS=failed exit=4 reason=…`. The job's stdout:
`jobsub_fetchlog -G annie --jobid <jobid> --unzipdir logs_<run>`. Test jobs always return the payload log; for
production WCSim and toolchain jobs, set `keep_failed_logs: true`.

**`status` failure mix**:
- "no dummy file": the job was lost or held, or never ran;
- "failed: exit 4 missing_outputs": the payload ran but did not produce its files (read the log);
- "finished but outputs missing in scratch": scratch eviction, or a transfer problem.

**jobsub fails with Python errors**: run from a clean shell. `mcprod` already strips `PYTHONPATH`/conda variables.
Avoid `setup jobsub_client` in the submitting shell; `mcprod check` warns if `jobsub_submit` isn't
`/opt/jobsub_lite`.

**Transfers**: `ifdh cp` failing with 401 on persistent → set `transfer.method: cp` (autoANNIE's experience).
dCache maintenance (often Wednesdays) breaks transfers: wait and rerun `copy`, which skips files already present.
dCache cannot overwrite: a size conflict is reported and left for you to resolve.

**`verify` stops with "tree missing from the 3 largest files"**: your toolchain doesn't fill that tree.
Set `toolchain.verify_trees` to the trees your files have (listed in the message).

**ROOT checks** run in the toolanalysis image with `python3.8` after `unset PYTHONPATH; source /usr/local/bin/thisroot.sh`.
Interactive equivalent:
```
singularity shell -B /pnfs:/pnfs,/exp/annie/app/users/$USER/temp_directory:/tmp,/exp/annie/data:/exp/annie/data,/exp/annie/app:/exp/annie/app /cvmfs/singularity.opensciencegrid.org/anniesoft/toolanalysis:latest/
```

**Logs**: `gunzip *.log.gz`.
