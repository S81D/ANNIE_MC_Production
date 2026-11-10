"""scratch -> persistent copies (ifdh or cp), POT summaries."""
import os
import re
import subprocess

from . import REPO, records, stages
from .grid import clean_env
from .records import say

IFDH_SETUP = "source /cvmfs/fermilab.opensciencegrid.org/products/common/etc/setup && setup ifdhc"
MANIFEST = re.compile(r"^(\d+)_.*_manifest\.json$")


def plan(cfg, stage, done_runs):
    """Files to copy [(src, dest_dir, size)], number already present, and size conflicts."""
    src_dir = stages.scratch_dir(cfg, stage)
    rules = [(stages.output_regex(t), cfg["layout"][stage][key], True)
             for t, key, _ in stages.outputs(cfg, stage).values()]
    rules.append((MANIFEST, cfg["layout"][stage]["logs"], False))
    todo, present, conflicts = [], 0, []
    for entry in sorted(os.scandir(src_dir), key=lambda e: e.name):
        for regex, dest, run_must_be_done in rules:
            match = regex.match(entry.name)
            if not match:
                continue
            if run_must_be_done and int(match.group(1)) not in done_runs:
                break
            size = entry.stat().st_size
            target = os.path.join(dest, entry.name)
            if os.path.exists(target):
                if os.path.getsize(target) == size:
                    present += 1
                else:
                    conflicts.append(target)
            else:
                todo.append((entry.path, dest, size))
            break
    return todo, present, conflicts


def _copy_batch(method, sources, dest):
    if method == "ifdh":
        cmd = ["bash", "-c", IFDH_SETUP + ' && ifdh cp -D "$@"', "ifdh_cp"] + sources + [dest + "/"]
    else:
        cmd = ["cp"] + sources + [dest + "/"]
    return subprocess.run(cmd, env=clean_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)


def copy(cfg, todo):
    """Copy in batches; returns list of files that failed (missing or wrong size afterwards)."""
    method, batch = cfg["transfer"]["method"], cfg["transfer"]["batch_size"]
    by_dest = {}
    for src, dest, size in todo:
        by_dest.setdefault(dest, []).append((src, size))
    failed, done = [], 0
    for dest, files in sorted(by_dest.items()):
        if not os.path.isdir(dest):
            os.makedirs(dest)
            os.chmod(dest, 0o777)            # as the old copy scripts did, so collaborators can write
        for i in range(0, len(files), batch):
            chunk = files[i:i + batch]
            proc = _copy_batch(method, [s for s, _ in chunk], dest)
            if proc.returncode != 0:
                say(proc.stdout.strip()[-2000:])
            for src, size in chunk:
                target = os.path.join(dest, os.path.basename(src))
                if not (os.path.exists(target) and os.path.getsize(target) == size):
                    failed.append(src)
            done += len(chunk)
            say("  copied %d / %d" % (done, len(todo)))
    return failed


def pot_outliers(files_dir, csv_dir, pattern):
    """[(run, value)] whose pot_N.csv is missing, non-numeric or far from the median (read_MC_POT.sh sums blindly)."""
    regex = stages.output_regex(pattern.replace("*", "{run}"))
    values = {}
    for entry in os.scandir(files_dir):
        match = regex.match(entry.name)
        if not match:
            continue
        run = int(match.group(1))
        try:
            with open(os.path.join(csv_dir, "pot_%d.csv" % run)) as handle:
                values[run] = float(handle.read().split(",")[1])
        except (OSError, IndexError, ValueError):
            values[run] = None
    good = sorted(v for v in values.values() if v and v > 0)
    if not good:
        return sorted(values.items())
    median = good[len(good) // 2]
    return sorted((r, v) for r, v in values.items() if not v or not 0.5 * median <= v <= 2 * median)


def pot_summary(cfg, stage):
    """Run helpers/read_MC_POT.sh over the persistent files; write the summary next to them."""
    if stage == "genie":
        files_dir, csv_dir = cfg["layout"]["genie"]["ghep"], cfg["layout"]["genie"]["pot"]
        pattern, out = "gntp.*.ghep.root", cfg["layout"]["genie"]["pot_summary"]
    else:
        files_dir = cfg["layout"]["toolchain"]["root"]
        csv_dir = cfg["toolchain"]["pot_input"] or cfg["layout"]["genie"]["pot"]
        pattern, out = "MC_*.root", cfg["layout"]["toolchain"]["pot_summary"]
    bad = pot_outliers(files_dir, csv_dir, pattern)
    if bad:
        raise SystemExit("POT summary NOT written: %d suspicious pot_N.csv value(s) (missing, non-numeric, or outside "
                         "0.5-2x the median, e.g. an extra digit), e.g. %s. Exact values: helpers/pot_from_ghep.py "
                         "(reads the gtree weight of gntp.N.ghep.root); fix the CSVs, then ./mcprod pot."
                         % (len(bad), bad[:10]))
    script = os.path.join(REPO, "helpers", "read_MC_POT.sh")
    proc = subprocess.run(["bash", script, files_dir, csv_dir, pattern], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True)
    if proc.returncode != 0:
        say(proc.stdout[-3000:])
        raise SystemExit("read_MC_POT.sh failed for %s" % files_dir)
    if os.path.exists(out):                  # never overwrite a summary someone may already cite
        out = out.replace(".txt", "_%s.txt" % records.now().replace(" ", "_").replace(":", ""))
    header = ("# POT summary — production %s, stage %s, %s\n# files: %s/%s   POT CSVs: %s\n\n"
              % (cfg["production"]["name"], stage, records.now(), files_dir, pattern, csv_dir))
    with open(out, "w") as handle:
        handle.write(header + proc.stdout)
    tail = "\n".join(proc.stdout.strip().splitlines()[-7:])
    return out, tail
