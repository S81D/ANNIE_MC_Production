"""ROOT-based checks run inside the ToolAnalysis container (ROOT 6.24 with PyROOT for python3.8)."""
import glob
import json
import os
import shlex
import subprocess

from . import REPO, records, stages
from .grid import clean_env
from .records import say

ROOT_ENV = "unset PYTHONPATH; source /usr/local/bin/thisroot.sh; "   # gpvm ifdhc PYTHONPATH leaks in otherwise
GUARD_FRACTION = 0.05


def exec_argv(cfg, script):
    tmp = cfg["paths"]["container_tmp"]
    os.makedirs(tmp, exist_ok=True)
    binds = ["/pnfs:/pnfs", tmp + ":/tmp", "/exp/annie/data:/exp/annie/data", "/exp/annie/app:/exp/annie/app"]
    if not REPO.startswith(("/exp/annie/app", "/exp/annie/data")):
        binds.append(REPO + ":" + REPO)
    return ["singularity", "exec", "-B", ",".join(binds), cfg["toolchain"]["container"].rstrip("/") + "/",
            "bash", "-c", ROOT_ENV + script]


def run(cfg, script, capture=True):
    return subprocess.run(exec_argv(cfg, script), env=clean_env(), universal_newlines=True,
                          stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None)


def probe_trees(cfg, files):
    """{file: set of TTree names} via rootls."""
    script = "; ".join('echo "== %s"; rootls %s' % (f, shlex.quote(f)) for f in files)
    out, trees, current = run(cfg, script).stdout, {}, None
    for line in out.splitlines():
        if line.startswith("== "):
            current = line[3:].strip()
            trees[current] = set()
        elif current:
            trees[current].update(line.split())
    return trees


def verify(cfg, stage, test=False):
    directory = stages.scratch_dir(cfg, stage, test)
    pattern, trees = stages.VERIFY_PATTERN[stage], cfg[stage]["verify_trees"]
    files = sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getsize, reverse=True)
    if not files:
        raise SystemExit("no %s files in %s" % (pattern, directory))
    # Guard: a tree missing even from the largest files is not filled by design — the checker would
    # otherwise flag (and purge would delete) every small-ish good file.
    probe = probe_trees(cfg, files[:3])
    absent = [t for t in trees if not any(t in found for found in probe.values())]
    if absent:
        raise SystemExit("required tree(s) %s are missing from the 3 largest files too — probably not filled "
                         "by design. Set %s.verify_trees to the trees your files contain: %s"
                         % (", ".join(absent), stage, sorted(set().union(*probe.values()))))
    out = os.path.join(records.stage_dir(cfg, stage, test), "broken_%s.txt" % records.now().replace(" ", "_"))
    script = "%s %s --pattern %s --trees %s --output %s" % (
        os.path.join(REPO, "helpers", "find_broken_rootfiles.sh"), shlex.quote(directory),
        shlex.quote(pattern), shlex.quote(" ".join(trees)), shlex.quote(out))
    proc = run(cfg, script, capture=False)
    if proc.returncode != 0:
        raise SystemExit("find_broken_rootfiles.sh failed (exit %d)" % proc.returncode)
    broken = []
    if os.path.exists(out):
        with open(out) as handle:
            broken = [line.strip() for line in handle if line.strip()]
    fraction = len(broken) / len(files)
    result = {"time": records.now(), "n_files": len(files), "n_broken": len(broken), "list": out if broken else None,
              "fraction": fraction, "blocked": fraction > GUARD_FRACTION, "trees": trees}
    records.set_state(cfg, stage, test, "verify", result)
    return result


def validate(cfg, stage, test_runs):
    out = os.path.join(records.stage_dir(cfg, stage, True), "validate.json")
    args = ["--stage", stage, "--test-dir", stages.scratch_dir(cfg, stage, True),
            "--ref-dir", cfg["validation"]["reference_dir"], "--runs", ",".join(str(r) for r in test_runs),
            "--json", out]
    if stage == "genie":
        args += ["--events", str(cfg["genie"]["events_per_job"]), "--volume", cfg["genie"]["volume"],
                 "--geometry", cfg["paths"]["geometry"]]
    elif stage == "anniedirt":
        args += ["--events", str(cfg["anniedirt"]["events_per_job"]), "--volume", cfg["genie"]["volume"],
                 "--pot-dir", stages.scratch_dir(cfg, "genie", True)]
    elif stage == "wcsim":
        args += ["--outputs", cfg["wcsim"]["outputs"], "--dirt-dir", stages.input_dirs(cfg, "wcsim", True)["dirt"][0]]
    else:
        args += ["--wcsim-dir", stages.input_dirs(cfg, "toolchain", True)["wcsim"][0]]
    script = "python3.8 %s %s" % (os.path.join(REPO, "validation", "validate.py"),
                                  " ".join(shlex.quote(a) for a in args))
    proc = run(cfg, script)
    if not os.path.exists(out):
        say(proc.stdout[-4000:])
        raise SystemExit("validate.py produced no result")
    with open(out) as handle:
        return json.load(handle), proc.stdout
