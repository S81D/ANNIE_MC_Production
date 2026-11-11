---
name: annie-mc-production
description: Run, monitor, recover, validate and transfer ANNIE MC production on the Fermilab grid (GENIE -> anniedirt -> WCSim -> MC toolchain) with ./mcprod and a production YAML. Use when asked to start or continue an ANNIE MC production, submit test or full jobs for a stage, check production status or completeness, launch recovery campaigns, validate test jobs, estimate grid resources, find/purge broken MC files, copy outputs to persistent, or write POT summaries.
---

# ANNIE MC production with `mcprod`

Repository root: this repo (on a gpvm usually `/exp/annie/app/users/$USER/ANNIE_MC_Production`). Everything goes
through `./mcprod <command> productions/<name>.yaml [stage]`. Read `docs/workflow.md` for the full procedure,
and `docs/configuration.md` for the keys.

## Hard rules

1. **Launch a stage — test or full — only when the previous stage is DONE.** Order: genie → anniedirt → wcsim →
   toolchain; each full stage also needs its own test stage DONE. Never pass `--ignore-gate` unless the user asks
   for it explicitly.
   - Test DONE: test jobs out of the queue, `validate` GREEN (or YELLOW reviewed with the user, then `--accept`),
     `estimate` applied to the YAML.
   - Full DONE: queue empty, ≥ 95 % complete, toolchain `verify`/`purge` done, `copy` finished.
2. Dry-run first (`submit … --dry-run`), and tell the user the **job count and data volume** before any real
   submission. Per run: GENIE ~25 MB, anniedirt ~0.5 MB, WCSim ~29 MB (+14 MB LAPPD), toolchain ~30 MB.
   Full chain for 4000 runs ≈ 0.4 TB. Never submit a campaign, transfer, purge or `--clear-scratch` without the
   user's go-ahead. Never use `--yes`.
3. Never delete or overwrite in persistent. `purge` and `--clear-scratch` act on this production's scratch
   area only, and only on the user's request.
4. Grid commands need an ANNIE gpvm (jobsub_lite, Kerberos + token). In a session without grid access, give the
   user complete copy-paste command blocks with real paths: no placeholders, no inline `#` comments (zsh).
   Add one line on the expected output.

## Workflow (per stage, in order)

```
./mcprod check    productions/X.yaml
./mcprod submit   productions/X.yaml <stage> --test        (10 jobs)
./mcprod status   productions/X.yaml <stage> --test
./mcprod validate productions/X.yaml <stage>               (GREEN / YELLOW / RED vs reference files)
./mcprod estimate productions/X.yaml <stage>               (paste the suggested resources into the YAML)
```
Run all four test stages first. Then the full production, one stage at a time, inside `screen`:
```
./mcprod submit   productions/X.yaml <stage>
./mcprod status   productions/X.yaml <stage>
./mcprod submit   productions/X.yaml <stage> --missing    (recovery, until >= 95 %)
./mcprod verify   productions/X.yaml toolchain             (toolchain only, then purge)
./mcprod copy     productions/X.yaml <stage>               (writes POT_summary.txt for genie/toolchain)
```

## Interpreting results

- `status`: expected = runs whose inputs exist; done = all outputs present; campaign table (initial, recovery N)
  with gains; failure mix from the dummy files. At ≥ 95 %, tell the user more recovery is optional and usually
  not worthwhile. A large or growing failure class (same exit or reason) needs a diagnosis, not resubmission.
- `validate`: RED means stop. YELLOW: list each item for the user (e.g. a toolchain tree missing by design,
  another GENIE build than the references) and let them decide before `--accept`. Toolchain checks are cautions
  only, except files with no entries in any tree (RED: the tree-maker config doesn't match the toolchain).
- `verify` stopping with "tree missing from the 3 largest files": the toolchain doesn't fill that tree. Propose
  a new `toolchain.verify_trees`; never purge in that state.
- Held jobs: memory is auto-released with +4 GB grace; for disk or walltime, raise `resources`, remove the held
  jobs (`jobsub_rm --constraint`, printed by `submit`/`status`), then `--missing`.
- POT sanity: about 1.13e17 per run.

## Facts worth knowing

- Seeds: deterministic = run (GENIE) or run + 1 (others); random = drawn at submission and recorded. Reruns on
  other worker nodes can diverge partway (floating point; not a bug, not a bias). For more
  statistics, use new run numbers plus `genie.flux_index_offset`, not reruns of the same flux files.
- Tank-volume GENIE is untested; recommend world.
- Toolchain config script (`toolchain.config_hook`): the repo's `toolchain/hooks/config_GENIE.py` (CC, default) or
  `config_GENIE_NC.py` (NC) is copied into the tarball, replacing its `config_GENIE.py`; `tarball` runs the tarball's
  own. Before a toolchain test, confirm with the user which script, and that its PhaseIITreeMaker settings match
  their toolchain. The dummy file says which script ran and whether it matched the tarball's copy.
- ROOT checks run in the toolanalysis image with `python3.8` after `source /usr/local/bin/thisroot.sh`.
- Records live in `records/<production>/` (not in git); `mcprod.log` has everything `mcprod` printed.
- Troubleshooting: `docs/troubleshooting.md`.
