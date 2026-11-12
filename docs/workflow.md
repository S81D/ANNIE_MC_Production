# Production workflow

**Rule: launch a stage — test or full — only when the previous stage is DONE.** `mcprod submit` checks this
(`--ignore-gate` overrides it, with a warning).

| | DONE when |
|---|---|
| Test stage | its 10 test jobs left the queue, `validate` is GREEN (or YELLOW reviewed and `--accept`ed), and the `estimate` result is in the YAML |
| Full stage | the queue is empty, ≥ 95 % of the expected runs are done, (toolchain) `verify`/`purge` are done, `copy` finished and was verified (GENIE and toolchain: POT summary written) |

Stage order: genie → anniedirt → wcsim → toolchain. A stage's inputs come from the previous stage: its test
outputs for `--test`, its persistent copy otherwise.

## A. Set up (once per production)

1. Choose the sample: `production.name`, runs (one per flux file, 0–3999), GENIE build, world volume.
2. Edit the toolchain config script for your analysis (`toolchain/hooks/config_GENIE.py` for CC,
   `config_GENIE_NC.py` for NC), or set `toolchain.config_hook: tarball`: see toolchain/README.md.
3. Check disk space (about 0.4 TB persistent for the full chain, plus scratch) and coordinate with the collaboration.
4. On a gpvm:
   ```
   kinit $USER@FNAL.GOV
   htgettoken -a htvaultprod.fnal.gov -i annie
   cd /exp/annie/app/users/$USER/ANNIE_MC_Production
   ./mcprod check productions/X.yaml
   ./mcprod tarball productions/X.yaml wcsim
   ./mcprod tarball productions/X.yaml toolchain
   ```
   (also `tarball … genie` for a custom GENIE build)

## B. Test the whole chain (10 runs, ~40 jobs, ~1 GB)

For each stage in order:
```
./mcprod submit   productions/X.yaml genie --test
./mcprod status   productions/X.yaml genie --test
./mcprod validate productions/X.yaml genie
./mcprod estimate productions/X.yaml genie
```
`submit --test` prints its job count and asks before submitting. Wait until `status` shows the jobs have left the
queue. If `validate` is YELLOW, explain each item, then `./mcprod validate … --accept`; never proceed on RED.
Paste the suggested resources into the YAML. Then repeat for anniedirt, wcsim and toolchain.
This catches a bad WCSim or ToolAnalysis tarball before 100 GB of GENIE output exists.

## C. Full production, one stage at a time

```
screen -S X_genie
./mcprod submit productions/X.yaml genie
```
It states the job count and data volume and asks for confirmation. About 4000 submissions take hours: detach
with `Ctrl-a d`, reattach with `screen -r X_genie`, or follow `tail -f records/X/mcprod.log`. A screen session
lives on one gpvm. Renew Kerberos (`kinit -R`) for sessions longer than about a day.

1. **While it runs**: `./mcprod status productions/X.yaml genie` now and then. Memory overruns are handled by
   auto-release (+4 GB grace). Investigate any other held job (`HoldReason`, docs/troubleshooting.md) rather than
   resubmitting it blindly.
2. **Recovery**: when the queue is empty, `status` gives the completeness and the failure mix. Below 95 %:
   ```
   ./mcprod submit productions/X.yaml genie --missing
   ```
   Each run of this is a recovery campaign; `status` lists every campaign with its gain. At ≥ 95 % the stage is
   done, and further recovery is optional and usually not worthwhile. Normalisation uses the POT of the runs
   present, so missing runs don't bias it, unless failures correlate with event content: check the failure mix.
3. **Toolchain only — before transfer**:
   ```
   ./mcprod verify productions/X.yaml toolchain
   ./mcprod purge  productions/X.yaml toolchain
   ```
   `purge` deletes only scratch files, after a y/N prompt. Purged runs become missing: run one more recovery, or
   accept them.
4. **Transfer** (in screen): `./mcprod copy productions/X.yaml genie`. The copy is size-verified, never
   overwrites, and writes `genie/POT_summary.txt` (toolchain: `MC_toolchain/<version>/POT_summary.txt`).
   Sanity check: about 1.13e17 POT per run, so about 4.5e20 for 4000 runs.
5. **Next stage** only after `copy` reports DONE.

## D. Wrap up

- Commit `productions/X.yaml`. `copy` puts a snapshot of `records/` into the persistent `logs/production_records/`.
- Announce the sample with its `MC_toolchain/<version>/POT_summary.txt`.
- Scratch expires on its own. Delete it deliberately only to relaunch a production of the same name: `submit`
  then stops, tells you what is there, and offers `--clear-scratch`.

## Seeds

`seeds.mode: deterministic` (default): GENIE seed = run, other stages = run + 1. A rerun starts identically, but
GENIE runs on different worker nodes can diverge partway. In the 2026-11 tests, 3 of 10 reruns diverged after
168–9805 of 20 000 events, while the seeds, the geometry scan and the earlier events were identical. The likely
cause is floating-point differences between CPU types; the manifest records the CPU. It is statistically
irrelevant: every run is a valid, independent sample. Bit-identical reruns are not guaranteed.
`random`: seeds are drawn at submission, unique within the production, and recorded in the dummy file and manifest.
For more statistics, use new run numbers (e.g. `runs.range: [100000, 103999]` with
`genie.flux_index_offset: 100000`). Note that re-using a flux file re-uses its flux entries.
