"""./mcprod <command> <production.yaml> [stage] [options]   (workflow: docs/workflow.md)"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

from . import REPO, STAGES, config, container, estimate, grid, records, stages, status, tarball, transfer
from .records import say


# ---- helpers -------------------------------------------------------------------------------------

def ask(question, answer="y"):
    try:
        reply = input("%s " % question).strip()
    except EOFError:
        return False
    return reply.lower() == answer.lower() if answer == "y" else reply == answer


def stage_inputs(cfg, stage, dry_run=False):
    """Copy the stage's worker files to {scratch}/_inputs/<stage>-<content hash>/ once; return their pnfs paths.
    A dry run only computes the paths."""
    staged, attached = stages.static_files(cfg, stage)
    files = [stages.executable(stage)] + staged
    digest = hashlib.sha1()
    for path in files:
        with open(path, "rb") as handle:
            digest.update(os.path.basename(path).encode() + handle.read())
    target = os.path.join(cfg["paths"]["scratch"], "_inputs", "%s-%s" % (stage, digest.hexdigest()[:10]))
    if not dry_run:
        os.makedirs(target, exist_ok=True)
    out = []
    for path in files:
        dest = os.path.join(target, os.path.basename(path))
        if not dry_run and not os.path.exists(dest):
            shutil.copyfile(path, dest)
            if dest.endswith((".sh", ".py")):
                os.chmod(dest, 0o755)
        out.append(dest)
    return out[0], out[1:], attached


def missing_files(paths):
    return [p for p in paths if p and not os.path.exists(p)]


def output_files(cfg, stage, test):
    """Files in the stage's scratch output dir that mcprod owns (outputs, dummies, manifests)."""
    directory = stages.scratch_dir(cfg, stage, test)
    regexes = [stages.output_regex(t) for t, _, _ in stages.outputs(cfg, stage).values()]
    regexes += [re.compile(r"^\d+_.*_(dummy_output|manifest\.json)$")]
    try:
        return sorted(e.path for e in os.scandir(directory) if any(r.match(e.name) for r in regexes))
    except FileNotFoundError:
        return []


# ---- commands --------------------------------------------------------------------------------------

def cmd_check(cfg, a):
    problems, notes = [], []
    say("production %s  (user %s, config %s)" % (cfg["production"]["name"], cfg["production"]["user"], cfg["_sha"]))
    say("  scratch:    " + cfg["paths"]["scratch"])
    say("  persistent: " + cfg["paths"]["persistent"])
    try:
        import yaml
        notes.append("PyYAML %s, Python %s" % (yaml.__version__, sys.version.split()[0]))
    except ImportError:
        problems.append("PyYAML missing")
    exe = shutil.which("jobsub_submit")
    if not exe:
        problems.append("jobsub_submit not found (run on an ANNIE gpvm)")
    elif not exe.startswith("/opt/jobsub_lite"):
        notes.append("jobsub_submit is %s (expected /opt/jobsub_lite/...): is an old jobsub_client set up?" % exe)
    if not shutil.which("klist") or subprocess.run(["klist", "-s"]).returncode != 0:
        notes.append("no valid Kerberos ticket: kinit $USER@FNAL.GOV")
    for stage in STAGES:
        c = cfg[stage]
        image = c["container"].rstrip("/")
        if os.path.isdir(image):
            notes.append("%-9s image %s -> %s" % (stage, os.path.basename(image), os.path.realpath(image)))
        else:
            problems.append("%s: container %s not found" % (stage, image))
        needed = stages.required_config(cfg, stage)
        unset = [k for k in needed if not c[k]]
        if unset:
            notes.append("%-9s not ready: set %s" % (stage, ", ".join(stage + "." + k for k in unset)))
        elif "tarball" in needed and not os.path.exists(c["tarball"]):
            problems.append("%s: tarball %s not found (./mcprod tarball ... %s)" % (stage, c["tarball"], stage))
    for label, path in (("flux_dir", cfg["paths"]["flux_dir"]), ("geometry", cfg["paths"]["geometry"]),
                        ("GENIE spline", cfg["genie"]["spline"]),
                        ("validation reference_dir", cfg["validation"]["reference_dir"])):
        if not os.path.exists(path):
            problems.append("%s not found: %s" % (label, path))
    if cfg["genie"]["volume"] == "tank":
        notes.append("CAUTION: tank-volume generation has never been tested; world (rock) generation is recommended")
    for line in notes:
        say("  note: " + line)
    for line in problems:
        say("  PROBLEM: " + line)
    say("check: %s" % ("OK" if not problems else "%d problem(s)" % len(problems)))
    return 1 if problems else 0


def cmd_tarball(cfg, a):
    info = tarball.build(cfg, a.stage)
    say("tarball %s  md5 %s  %.0f MB" % (info["tarball"], info["md5"], info["bytes"] / 1e6))
    if info.get("git"):
        say("  source commit %s (%s)%s" % (info["git"]["commit"][:10], info["git"]["branch"],
                                           " DIRTY" if info["git"]["dirty"] else ""))
    else:
        say("  source is not a git checkout: only its path and md5 are recorded")
    return 0


def cmd_submit(cfg, a):
    stage, test = a.stage, a.test
    config.require(cfg, stage, *stages.required_config(cfg, stage))
    problems = records.gate(cfg, stage, test)
    for p in problems:
        say(("WARNING (--ignore-gate): " if a.ignore_gate else "BLOCKED: ") + p)
    if problems and not a.ignore_gate:
        say("Launch a stage only when the previous stage is DONE (docs/workflow.md).")
        return 1
    if stage == "genie" and not test and not records.chain_test_done(cfg):
        say("reminder: the full test chain (all four stages --test) is not DONE yet; recommended before a full GENIE run")
    if cfg["genie"]["volume"] == "tank":
        say("CAUTION: tank-volume generation has never been tested; world (rock) generation is recommended")

    runs = status.selected_runs(cfg, test)
    if a.runs:
        runs = sorted({int(r) for r in a.runs.split(",")})
    expected = status.expected(cfg, stage, test, runs)
    done_runs = status.done(cfg, stage, test) & set(runs)
    no_input = sorted(set(runs) - expected)
    if no_input:
        say("%d run(s) have missing inputs and are skipped, e.g. %s" % (len(no_input), no_input[:10]))
    existing = output_files(cfg, stage, test)
    if a.missing or a.runs:
        candidates = sorted(expected - done_runs)
    elif existing and not a.clear_scratch:
        say("%s already holds %d file(s) of this stage. Choose one:" % (stages.scratch_dir(cfg, stage, test),
                                                                        len(existing)))
        say("  --missing        treat this as a recovery campaign (submit only runs without outputs)")
        say("  new name         set another production.name in the YAML")
        say("  --clear-scratch  delete those files first (asks for confirmation)")
        return 1
    else:
        candidates = sorted(expected)
    if a.clear_scratch and existing:
        say("About to DELETE %d file(s) from %s, e.g. %s" % (len(existing), stages.scratch_dir(cfg, stage, test),
                                                            [os.path.basename(p) for p in existing[:3]]))
        if not ask("Type 'delete %d' to confirm:" % len(existing), "delete %d" % len(existing)):
            say("aborted; nothing deleted")
            return 1
        for path in existing:
            os.remove(path)
        say("deleted %d file(s)" % len(existing))
        candidates = sorted(expected)

    if not a.dry_run and not a.skip_queue_check and candidates:
        say("checking the queue (jobsub_q, polled twice 60 s apart) ...")
        queued = grid.queued_runs(cfg, stage, test)
        if queued is None:
            say("jobsub_q failed: cannot tell which runs are still running. Retry, or use --skip-queue-check.")
            return 1
        held = sorted(r for r, h in queued.items() if h)
        if held:
            say("%d held job(s), e.g. runs %s. Inspect: jobsub_q -G %s --user %s -af JobsubJobId HoldReason" % (
                len(held), held[:10], cfg["production"]["group"], cfg["production"]["user"]))
            say("Remove them before resubmitting: jobsub_rm -G %s --constraint 'JobStatus==5 && Owner==\"%s\"'"
                % (cfg["production"]["group"], cfg["production"]["user"]))
        candidates = [r for r in candidates if r not in queued]
    if not candidates:
        say("nothing to submit")
        return 0

    seeds = records.make_seeds(cfg, stage, candidates, test)
    commit = grid.git_commit()
    if commit.endswith("+dirty") and not test:
        say("note: this repo has uncommitted changes (%s); they are recorded in every manifest" % commit)
    exe, staged, attached = stage_inputs(cfg, stage, a.dry_run)
    missing = missing_files(attached)
    if missing:
        say("missing input(s): %s" % missing)
        return 1
    tarballs, extra = [], {}
    for path in attached:
        if a.dry_run:
            say("  tarball %s (md5 recorded at submission)" % path)
            continue
        info = tarball.fingerprint(cfg, path)
        tarballs.append(info)
        extra["tarball_md5"] = info["md5"]
        say("  tarball %s  md5 %s  %.0f MB  (%s)" % (path, info["md5"], info["bytes"] / 1e6, info["built_by"]))
    outdir = stages.scratch_dir(cfg, stage, test)
    res = cfg[stage]["resources"]
    volume_mb = stages.MB_PER_RUN[stage] * len(candidates)
    if stage == "wcsim" and cfg["wcsim"]["outputs"] == "both":
        volume_mb += stages.MB_PER_RUN["wcsim_lappd"] * len(candidates)
    kind = records.next_kind(cfg, stage, test, a.missing)
    say("%s %s: %d job(s) -> %s" % (kind, stage, len(candidates), outdir))
    say("  resources %s / %s / %s, %s, seeds %s, ~%.1f GB of output" % (
        res["memory"], res["disk"], res["lifetime"], cfg["grid"]["site"], cfg["seeds"]["mode"], volume_mb / 1024))
    if a.dry_run:
        for run in candidates[:3]:
            argv = grid.submit_argv(cfg, stage, staged + attached + stages.run_inputs(cfg, stage, run, test), outdir,
                                    exe, stages.job_args(cfg, stage, run, seeds[run], test, commit), no_submit=True)
            say(" ".join(argv))
        say("dry run: nothing submitted (%d command(s) built)" % len(candidates))
        return 0
    if len(candidates) > cfg["grid"]["confirm_above"] and not a.yes:
        if not ask("Submit %d jobs? [y/N]" % len(candidates)):
            say("aborted")
            return 1
    os.makedirs(outdir, exist_ok=True)
    camp = records.start_campaign(cfg, stage, test, kind, candidates, len(expected), len(done_runs), commit)
    camp["tarballs"] = tarballs
    n_ok = n_fail = 0
    try:
        for i, run in enumerate(candidates, 1):
            args = stages.job_args(cfg, stage, run, seeds[run], test, commit)
            args.update(extra)
            argv = grid.submit_argv(cfg, stage, staged + attached + stages.run_inputs(cfg, stage, run, test), outdir,
                                    exe, args)
            jobid, output = grid.submit(argv)
            records.record_job(camp, {"run": run, "seed": seeds[run], "jobid": jobid, "time": records.now(),
                                      "error": None if jobid else output[-1500:]})
            if jobid:
                n_ok += 1
            else:
                n_fail += 1
                say("  run %d: submission FAILED\n%s" % (run, output[-800:]))
            if i % 25 == 0 or i == len(candidates):
                say("  %d / %d submitted (%d failed)" % (i, len(candidates), n_fail))
    except KeyboardInterrupt:
        say("interrupted: %d submitted so far are recorded" % n_ok)
    records.finish_campaign(cfg, stage, test, camp, n_ok, n_fail)
    say("%s: %d job(s) submitted, %d failed. Follow with ./mcprod status %s %s%s" % (
        kind, n_ok, n_fail, os.path.basename(cfg["_file"]), stage, " --test" if test else ""))
    return 0 if n_fail == 0 else 1


def cmd_status(cfg, a):
    queued = None if a.skip_queue_check else grid.queued_runs(cfg, a.stage, a.test, repoll=0)
    summary, lines = status.report(cfg, a.stage, a.test, queued)
    for line in lines:
        say(line)
    if queued is None and not a.skip_queue_check:
        say("  (jobsub_q unavailable: queue state unknown)")
    return 0


def cmd_validate(cfg, a):
    if a.accept:
        val = records.state(cfg, a.stage, True).get("validate")
        if not val or val["verdict"] != "YELLOW":
            say("nothing to accept: last verdict is %s" % (val or {}).get("verdict"))
            return 1
        val["accepted"] = records.now()
        records.set_state(cfg, a.stage, True, "validate", val)
        say("YELLOW validation of test %s accepted" % a.stage)
        return 0
    result, _ = container.validate(cfg, a.stage, config.test_runs(cfg))
    for check in result["checks"]:
        say("  %-6s %-28s %s" % (check["level"], check["name"], check["message"]))
    verdict = result["verdict"]
    advice = {"GREEN": "reasonable to proceed", "YELLOW": "review the flagged items; if understood: --accept",
              "RED": "do not proceed"}[verdict]
    say("validate %s: %s — %s" % (a.stage, verdict, advice))
    records.set_state(cfg, a.stage, True, "validate", {"verdict": verdict, "time": records.now(),
                                                       "checks": result["checks"]})
    return 0 if verdict != "RED" else 1


def cmd_estimate(cfg, a):
    _, lines = estimate.report(cfg, a.stage)
    for line in lines:
        say(line)
    say("  cross-check with HTCondor: jobsub_q -G %s --user %s -af JobsubJobId ResidentSetSize_RAW MemoryUsage "
        "DiskUsage_RAW RequestDisk" % (cfg["production"]["group"], cfg["production"]["user"]))
    return 0


def cmd_verify(cfg, a):
    result = container.verify(cfg, a.stage, a.test)
    say("verify %s: %d of %d file(s) broken (%.1f %%)%s" % (
        a.stage, result["n_broken"], result["n_files"], 100 * result["fraction"],
        ("; list: " + result["list"]) if result["list"] else ""))
    if result["blocked"]:
        say("  more than %.0f %% flagged: purge is blocked. Check whether a tree is simply not filled by your "
            "toolchain (%s.verify_trees)." % (100 * container.GUARD_FRACTION, a.stage))
    elif result["list"]:
        say("  next: ./mcprod purge %s %s --list %s" % (os.path.basename(cfg["_file"]), a.stage, result["list"]))
    return 0


def cmd_purge(cfg, a):
    ver = records.state(cfg, a.stage, a.test).get("verify")
    if not ver:
        say("run ./mcprod verify first")
        return 1
    if ver["blocked"] and not a.force:
        say("purge blocked: last verify flagged %.1f %% of files (see verify output). --force overrides." %
            (100 * ver["fraction"]))
        return 1
    listing = a.list or ver.get("list")
    if not listing:
        say("no broken files listed")
        return 0
    root = os.path.realpath(stages.scratch_dir(cfg, a.stage, a.test)) + os.sep
    with open(listing) as handle:
        paths = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    outside = [p for p in paths if not os.path.realpath(p).startswith(root)]
    if outside:
        say("refusing: %d path(s) outside %s, e.g. %s" % (len(outside), root, outside[:3]))
        return 1
    script = os.path.join(REPO, "helpers", "delete_broken_rootfiles.sh")
    proc = subprocess.run(["bash", "-c", transfer.IFDH_SETUP + ' && bash "$@"', "purge", script, listing],
                          env=grid.clean_env())
    records.set_state(cfg, a.stage, a.test, "purge", {"time": records.now(), "list": listing,
                                                      "exit": proc.returncode})
    return proc.returncode


def cmd_copy(cfg, a):
    stage = a.stage
    if not a.skip_queue_check:
        queued = grid.queued_runs(cfg, stage, False)
        if queued is None:
            say("jobsub_q failed: cannot confirm the queue is empty (--skip-queue-check to override)")
            return 1
        if queued:
            say("%d job(s) of this stage are still in the queue: wait, or remove held ones first" % len(queued))
            return 1
    summary, lines = status.report(cfg, stage, False)
    say(lines[2].strip())
    if summary["fraction"] < cfg["recovery"]["complete_fraction"] and not a.accept_incomplete:
        say("below %.0f %% complete: run recovery (--missing) first, or pass --accept-incomplete" %
            (100 * cfg["recovery"]["complete_fraction"]))
        return 1
    if stage == "toolchain" and not a.skip_verify:
        st = records.state(cfg, stage, False)
        last = max((c["started"] for c in records.campaigns(cfg, stage, False)), default="")
        if not st.get("verify") or st["verify"]["time"] < last:
            say("run ./mcprod verify (and purge) after the last campaign before copying (--skip-verify overrides)")
            return 1
    todo, present, conflicts = transfer.plan(cfg, stage, summary["done_runs"])
    say("copy %s: %d file(s) to copy, %d already in persistent, %d size conflict(s)" % (
        stage, len(todo), present, len(conflicts)))
    for path in conflicts[:10]:
        say("  conflict (left untouched): " + path)
    failed = transfer.copy(cfg, todo) if todo else []
    if failed:
        say("%d file(s) did not copy correctly, e.g. %s — rerun copy" % (len(failed), failed[:5]))
        return 1
    snapshot = os.path.join(cfg["layout"][stage]["logs"], "production_records",
                            records.now().replace(" ", "_").replace(":", ""))
    shutil.copytree(records.stage_dir(cfg, stage, False), snapshot)
    info = {"completed": records.now(), "files": len(todo) + present, "fraction": summary["fraction"],
            "conflicts": len(conflicts)}
    if stage in ("genie", "toolchain"):
        out, tail = transfer.pot_summary(cfg, stage)
        info["pot_summary"] = out
        say("POT summary written: %s\n%s" % (out, tail))
    records.set_state(cfg, stage, False, "copy", info)
    say("copy %s: DONE (%d files in persistent). The next stage can be launched." % (stage, info["files"]))
    return 0


def cmd_pot(cfg, a):
    if a.stage not in ("genie", "toolchain"):
        say("POT summaries exist for genie and toolchain")
        return 1
    out, tail = transfer.pot_summary(cfg, a.stage)
    say("written %s\n%s" % (out, tail))
    return 0


COMMANDS = {"check": cmd_check, "tarball": cmd_tarball, "submit": cmd_submit, "status": cmd_status,
            "validate": cmd_validate, "estimate": cmd_estimate, "verify": cmd_verify, "purge": cmd_purge,
            "copy": cmd_copy, "pot": cmd_pot}
NEEDS_STAGE = set(COMMANDS) - {"check"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="mcprod", description=__doc__)
    p.add_argument("command", choices=sorted(COMMANDS))
    p.add_argument("config", help="productions/<name>.yaml")
    p.add_argument("stage", nargs="?", choices=STAGES)
    p.add_argument("--test", action="store_true", help="the 10-job test campaign of the stage")
    p.add_argument("--dry-run", action="store_true", help="build and print jobsub commands, submit nothing")
    p.add_argument("--runs", help="comma-separated run numbers (re-processing specific runs)")
    p.add_argument("--missing", action="store_true", help="recovery: only runs without outputs")
    p.add_argument("--clear-scratch", action="store_true", help="delete this stage's existing scratch files first")
    p.add_argument("--ignore-gate", action="store_true", help="submit although the previous stage is not DONE")
    p.add_argument("--skip-queue-check", action="store_true", help="do not query jobsub_q")
    p.add_argument("--yes", action="store_true", help="do not ask before submitting many jobs")
    p.add_argument("--accept", action="store_true", help="validate: accept a reviewed YELLOW verdict")
    p.add_argument("--list", help="purge: file with the paths to delete (default: last verify list)")
    p.add_argument("--force", action="store_true", help="purge although verify flagged too many files")
    p.add_argument("--accept-incomplete", action="store_true", help="copy below the completeness threshold")
    p.add_argument("--skip-verify", action="store_true", help="copy toolchain output without a verify")
    a = p.parse_args(argv)
    if a.command in NEEDS_STAGE and not a.stage:
        p.error("%s needs a stage (%s)" % (a.command, ", ".join(STAGES)))
    try:
        cfg = config.load(a.config)
    except (config.ConfigError, OSError) as err:
        print("config error: %s" % err)
        return 2
    records.open_log(cfg)
    try:
        return COMMANDS[a.command](cfg, a)
    except config.ConfigError as err:
        say("config error: %s" % err)
        return 2
