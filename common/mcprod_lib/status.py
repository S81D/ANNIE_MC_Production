"""Which runs are expected, done, missing; campaign history; failure mix."""
import os
import re

from . import records, stages
from .config import runs as config_runs, test_runs


def scan(directory, regex):
    """Run numbers of files in directory matching regex (one capture group)."""
    found = set()
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                match = regex.match(entry.name)
                if match:
                    found.add(int(match.group(1)))
    except FileNotFoundError:
        pass
    return found


def selected_runs(cfg, test):
    return test_runs(cfg) if test else config_runs(cfg)


def expected(cfg, stage, test, runs):
    """Runs whose inputs all exist."""
    have = set(runs)
    for label, (directory, template) in stages.input_dirs(cfg, stage, test).items():
        if stage == "genie":
            flux = stages.output_regex(cfg["genie"]["flux_file"].replace("{index}", "{run}"))
            offset = cfg["genie"]["flux_index_offset"]
            have &= {index + offset for index in scan(directory, flux)}
        else:
            have &= scan(directory, stages.output_regex(template))
    return have


def outputs_present(cfg, stage, test):
    """kind -> runs present, in scratch and (production only) persistent."""
    present = {}
    for kind, (template, layout_key, _) in stages.outputs(cfg, stage).items():
        regex = stages.output_regex(template)
        runs = scan(stages.scratch_dir(cfg, stage, test), regex)
        if not test:
            runs |= scan(cfg["layout"][stage][layout_key], regex)
        present[kind] = runs
    return present


def done(cfg, stage, test, present=None):
    present = present or outputs_present(cfg, stage, test)
    required = [k for k, (_, _, req) in stages.outputs(cfg, stage).items() if req]
    result = None
    for kind in required:
        result = present[kind] if result is None else result & present[kind]
    return result or set()


def failure_mix(cfg, stage, test, failed_runs):
    """Classify runs that were submitted but have no outputs, from their dummy files."""
    regex = re.compile(r"^(\d+)_.*_dummy_output$")
    latest = {}
    directory = stages.scratch_dir(cfg, stage, test)
    try:
        for entry in os.scandir(directory):
            match = regex.match(entry.name)
            if match and int(match.group(1)) in failed_runs:
                run = int(match.group(1))
                if run not in latest or entry.stat().st_mtime > latest[run].stat().st_mtime:
                    latest[run] = entry
    except FileNotFoundError:
        pass
    mix = {}
    for run in failed_runs:
        reason = "no dummy file (lost, held or never ran)"
        if run in latest:
            with open(latest[run].path, errors="replace") as handle:
                tail = handle.read()[-2000:]
            match = re.search(r"MCPROD_STATUS=(\w+)(?: exit=(\d+))?(?: reason=(\S+))?", tail)
            if not match:
                reason = "job did not finish (no status line)"
            elif match.group(1) == "failed":
                reason = "failed: exit %s %s" % (match.group(2), (match.group(3) or "").replace("_", " "))
            else:
                reason = "finished but outputs missing in scratch"
        mix.setdefault(reason, []).append(run)
    return mix


def campaign_table(cfg, stage, test, done_runs):
    """[(kind, date, jobs, done_after, gain)] with done_after = done before + this campaign's runs now done.
    A done run counts for the last campaign that submitted it (a recovery or a rerun after --clear-scratch)."""
    camps = records.campaigns(cfg, stage, test)
    submitted = [{j["run"] for j in records.jobs(camp) if j.get("jobid")} for camp in camps]
    rows = []
    for i, camp in enumerate(camps):
        later = set().union(*submitted[i + 1:])
        gained = len((submitted[i] - later) & done_runs)
        rows.append((camp["kind"], camp["started"][:10], len(submitted[i]), camp["n_done_before"] + gained, gained))
    return rows


def report(cfg, stage, test, queued=None):
    """Return (summary dict, printable lines)."""
    runs = selected_runs(cfg, test)
    exp = expected(cfg, stage, test, runs)
    present = outputs_present(cfg, stage, test)
    done_runs = done(cfg, stage, test, present) & set(runs)
    in_scratch = done_runs & scan_required(cfg, stage, test)
    frac = len(done_runs) / len(exp) if exp else 0.0
    missing = sorted(exp - done_runs)
    lines = ["%s%s — %s" % ("TEST " if test else "", stage, cfg["production"]["name"]),
             "  expected (inputs present): %d of %d runs" % (len(exp), len(runs)),
             "  done: %d (%.1f %%)   in scratch: %d   persistent only: %d" % (
                 len(done_runs), 100 * frac, len(in_scratch), len(done_runs - in_scratch))]
    if queued is not None:
        held = sorted(r for r, h in queued.items() if h)
        lines.append("  in queue: %d   held: %d%s" % (len(queued), len(held), (" -> runs %s" % held[:20]) if held else ""))
    table = campaign_table(cfg, stage, test, done_runs)
    if table:
        lines.append("  %-14s %-11s %6s %12s %6s" % ("campaign", "date", "jobs", "done after", "gain"))
        for kind, date, njobs, after, gain in table:
            pct = 100.0 * after / len(exp) if exp else 0.0
            lines.append("  %-14s %-11s %6d %6d (%4.1f%%) %+6d" % (kind, date, njobs, after, pct, gain))
    submitted = set()
    for camp in records.campaigns(cfg, stage, test):
        submitted |= {j["run"] for j in records.jobs(camp) if j.get("jobid")}
        if camp.get("cleared"):
            lines.append("  (%s %s deleted %d earlier scratch file(s) first: --clear-scratch)" % (
                camp["kind"], camp["started"][:10], camp["cleared"]))
    failed = (submitted & exp) - done_runs - set(queued or {})
    if failed:
        lines.append("  failure mix of %d submitted runs without outputs:" % len(failed))
        for reason, rs in sorted(failure_mix(cfg, stage, test, failed).items(), key=lambda kv: -len(kv[1])):
            lines.append("    %4d  %s   e.g. runs %s" % (len(rs), reason, sorted(rs)[:8]))
    threshold = cfg["recovery"]["complete_fraction"]
    if exp and frac >= threshold:
        lines.append("  DONE-level completeness (>= %.0f %%): further recovery is optional and usually not "
                     "worthwhile." % (100 * threshold))
    elif missing:
        lines.append("  %d runs missing; next: ./mcprod submit %s %s%s%s" % (
            len(missing), os.path.basename(cfg["_file"]), stage, " --test" if test else "",
            " --missing" if records.campaigns(cfg, stage, test) else ""))
    summary = {"expected": len(exp), "done": len(done_runs), "fraction": frac, "missing": missing,
               "done_runs": done_runs, "expected_runs": exp}
    return summary, lines


def scan_required(cfg, stage, test):
    result = None
    for kind, (template, _, req) in stages.outputs(cfg, stage).items():
        if req:
            found = scan(stages.scratch_dir(cfg, stage, test), stages.output_regex(template))
            result = found if result is None else result & found
    return result or set()
