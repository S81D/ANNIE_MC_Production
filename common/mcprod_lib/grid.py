"""jobsub_lite calls: build/submit jobs and read the queue."""
import os
import re
import subprocess
import time

from . import REPO
from .config import parse_mb

# Same attribute list as autoANNIE's lib/monitor_jobs.py (tested on ANNIE data jobs).
Q_ATTRS = ["JobsubJobId", "JobStatus", "MemoryUsage", "RequestMemory", "DiskUsage", "RequestDisk",
           "Args", "Arguments", "Owner", "AcctGroupUser", "ResidentSetSize_RAW", "DiskUsage_RAW"]
JOBID = re.compile(r"(\d+\.\d+@jobsub\w*\.fnal\.gov)")


def clean_env():
    """jobsub_lite/ifdh have their own Python; inherited Python/conda variables break them."""
    env = dict(os.environ)
    for key in list(env):
        if key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV") or key.startswith(("CONDA", "PIXI_", "MAMBA_")):
            env.pop(key)
    return env


def git_commit():
    """Short commit of this repo, with '+dirty' if there are uncommitted changes."""
    try:
        commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, universal_newlines=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--untracked-files=no"],
                               stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
        return commit + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def submit_argv(cfg, stage, files, outdir, exe, args, no_submit=False):
    res, grid = cfg[stage]["resources"], cfg["grid"]
    argv = ["jobsub_submit", "-G", cfg["production"]["group"],
            "--memory=%dMB" % parse_mb(res["memory"]), "--disk=" + res["disk"].replace(" ", ""),
            "--expected-lifetime=" + res["lifetime"].replace(" ", "")]
    if grid["site"] == "onsite":
        argv.append("--resource-provides=usage_model=DEDICATED,OPPORTUNISTIC")
    else:
        argv += ["--resource-provides=usage_model=OFFSITE", "--blacklist=" + ",".join(grid["offsite_blacklist"])]
    if grid["auto_release"]:
        argv.append("--lines=+FERMIHTC_AutoRelease=True")
    if grid["grace_memory"]:
        argv.append("--lines=+FERMIHTC_GraceMemory=%d" % parse_mb(grid["grace_memory"]))
    for path in files:
        argv += ["-f", path]
    argv += ["-d", "OUTPUT", outdir]
    if no_submit:
        argv.append("--no_submit")          # must come before file://, or jobsub passes it to the worker
    argv.append("file://" + exe)
    argv += ["%s=%s" % (key, value) for key, value in args.items()]
    return argv


def submit(argv):
    """Run jobsub_submit; returns (jobid or None, combined output)."""
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                              env=clean_env(), timeout=600)
    except (OSError, subprocess.SubprocessError) as err:
        return None, str(err)
    match = JOBID.search(proc.stdout)
    return (match.group(1) if match and proc.returncode == 0 else None), proc.stdout


def parse_args(text):
    return dict(re.findall(r"(\w+)=(\S+)", text))


def queue(user, group="annie"):
    """Our jobs in the queue as dicts, or None if jobsub_q failed."""
    try:
        out = subprocess.run(["jobsub_q", "-G", group, "--user", user, "-af:t"] + Q_ATTRS,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
                             env=clean_env(), timeout=600, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    jobs = []
    for line in out.splitlines():
        fields = line.split("\t")
        if len(fields) < len(Q_ATTRS) or not fields[1].isdigit():
            continue
        args = parse_args(fields[6] + " " + fields[7])
        if "production" not in args or "run" not in args:
            continue
        jobs.append({"id": fields[0], "status": int(fields[1]), "held": fields[1] == "5",
                     "production": args["production"], "stage": args.get("stage"),
                     "run": int(args["run"]), "test": args.get("test") == "1"})
    return jobs


def queued_runs(cfg, stage, test, repoll=60):
    """{run: held?} for this production/stage still in the queue. Polls twice (jobsub_q can miss fresh jobs)."""
    found = {}
    for attempt in (0, 1):
        jobs = queue(cfg["production"]["user"], cfg["production"]["group"])
        if jobs is None:
            return None
        for job in jobs:
            if job["production"] == cfg["production"]["name"] and job["stage"] == stage and job["test"] == test:
                found[job["run"]] = found.get(job["run"], False) or job["held"]
        if attempt == 0 and repoll:
            time.sleep(repoll)
    return found
