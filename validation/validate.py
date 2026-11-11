#!/usr/bin/env python3
"""GREEN / YELLOW / RED sanity checks of one stage's test-job outputs against reference files.

Not an exact comparison: the aim is "does this look reasonable before a full production?".
Runs in the toolanalysis image (python3.8 + PyROOT, standard library only), called by `mcprod validate`.
"""
import argparse
import csv
import glob
import json
import os
import re
import statistics

import ROOT

ROOT.gErrorIgnoreLevel = ROOT.kError           # GENIE classes have no dictionary here; that is fine
GREEN, YELLOW, RED = "GREEN", "YELLOW", "RED"


class Report(object):
    def __init__(self, stage):
        self.stage, self.checks = stage, []

    def add(self, level, name, message):
        self.checks.append({"level": level, "name": name, "message": message})

    def verdict(self):
        levels = [c["level"] for c in self.checks]
        return RED if RED in levels else YELLOW if YELLOW in levels else GREEN


def open_root(path):
    """TFile or None (ROOT 6.24 returns a null/zombie file, newer ROOT raises)."""
    try:
        handle = ROOT.TFile.Open(path)
    except OSError:
        return None
    if not handle or handle.IsZombie():
        return None
    return handle


def tree_names(handle):
    return {k.GetName() for k in handle.GetListOfKeys() if k.GetClassName() in ("TTree", "TNtuple")}


def entries(handle, name):
    tree = handle.Get(name)
    return int(tree.GetEntries()) if tree else None


def column(tree, expr):
    tree.SetEstimate(tree.GetEntries() + 1)
    n = tree.Draw(expr, "", "goff")
    buf = tree.GetV1()
    return [buf[i] for i in range(n)]


def as_text(value):
    """char[] branches come back as a buffer from PyROOT."""
    if isinstance(value, str):
        return value
    try:
        return bytes(value).split(b"\0")[0].decode(errors="replace")
    except (TypeError, ValueError):
        return str(value)


def mean(values):
    return sum(values) / len(values) if values else float("nan")


def compare(report, name, test, ref, rel=None, absolute=None, unit="", caution=False):
    """YELLOW if test differs from the reference by more than the tolerance."""
    if ref is None or test is None:
        report.add(YELLOW, name, "no reference value")
        return
    diff = abs(test - ref)
    bad = (rel is not None and ref != 0 and diff / abs(ref) > rel) or (absolute is not None and diff > absolute)
    tol = ("±%.0f %%" % (100 * rel)) if rel is not None else ("±%g" % absolute)
    message = "%.4g%s vs reference %.4g%s (tolerance %s)" % (test, unit, ref, unit, tol)
    report.add(YELLOW if bad else GREEN, name, ("CAUTION: " + message) if bad and caution else message)


def world_half_lengths(gdml):
    """Half-lengths (m) of the WORLD_S box in the GDML geometry, or None."""
    try:
        text = open(gdml).read()
    except (OSError, TypeError):
        return None
    box = re.search(r'<box[^>]*name="WORLD_S"[^>]*>', text)
    if not box:
        return None
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', box.group(0)))
    scale = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}.get(attrs.get("lunit", "mm"), 1e-3)
    return {"vtxx": float(attrs["x"]) * scale / 2, "vtxy": float(attrs["y"]) * scale / 2,
            "vtxz": float(attrs["z"]) * scale / 2}


def run_files(directory, template, runs):
    """{run: path} for runs whose file exists."""
    found = {}
    for run in runs:
        path = os.path.join(directory, template.format(run=run))
        if os.path.exists(path):
            found[run] = path
    return found


def completeness(report, label, found, runs, required=True):
    n = len(found)
    if n == len(runs):
        report.add(GREEN, label, "%d / %d test runs" % (n, len(runs)))
    elif n == 0:
        report.add(RED if required else YELLOW, label, "none of the %d test runs" % len(runs))
    else:
        missing = sorted(set(runs) - set(found))
        report.add(YELLOW, label, "%d / %d test runs (missing %s)" % (n, len(runs), missing[:10]))


def read_pot(path):
    with open(path) as handle:
        row = next(csv.reader(handle), None)
    try:
        return float(row[1])
    except (TypeError, IndexError, ValueError):
        return None


# ---- stages -----------------------------------------------------------------------------------------

def genie_stats(paths):
    ev, cc, numu, vtxt, n, targets = [], 0, 0, [], 0, {}
    extent = {"vtxx": [1e9, -1e9], "vtxy": [1e9, -1e9], "vtxz": [1e9, -1e9]}
    for path in paths:
        handle = open_root(path)
        tree = handle.Get("gst") if handle else None
        if not tree:
            continue
        n += int(tree.GetEntries())
        ev += column(tree, "Ev")
        cc += int(tree.GetEntries("cc"))
        numu += int(tree.GetEntries("neu==14"))
        vtxt += column(tree, "vtxt")
        for tgt in column(tree, "tgt"):
            targets[int(tgt)] = targets.get(int(tgt), 0) + 1
        for axis in extent:
            values = column(tree, axis)
            extent[axis] = [min(extent[axis][0], min(values)), max(extent[axis][1], max(values))]
        handle.Close()
    if not n:
        return None
    return {"n": n, "ev": mean(ev), "cc": cc / float(n), "numu": numu / float(n),
            "vtxt_median": statistics.median(vtxt), "targets": {k: v / float(n) for k, v in targets.items()},
            "extent": extent}


def check_genie(report, a, runs):
    ghep = run_files(a.test_dir, "gntp.{run}.ghep.root", runs)
    gst = run_files(a.test_dir, "gntp.{run}.gst.root", runs)
    pot = run_files(a.test_dir, "pot_{run}.csv", runs)
    completeness(report, "ghep files", ghep, runs)
    completeness(report, "gst files", gst, runs)
    completeness(report, "POT csv files", pot, runs)
    for label, template in (("ghep logs", "gntp.{run}.ghep.log.gz"), ("maxpl files", "ANNIE-{run}.maxpl.xml"),
                            ("BNBFlux files", "BNBFlux{run}.xml")):
        completeness(report, label, run_files(a.test_dir, template, runs), runs, required=False)
    for label, files, tree in (("ghep events", ghep, "gtree"), ("gst events", gst, "gst")):
        wrong = []
        for run, path in files.items():
            handle = open_root(path)
            n = entries(handle, tree) if handle else None
            if n != a.events:
                wrong.append((run, n))
        report.add(RED if wrong else GREEN, label,
                   ("runs with != %d events: %s" % (a.events, wrong[:5])) if wrong else "%d per file" % a.events)
    pots = {run: read_pot(path) for run, path in pot.items()}
    bad = [run for run, value in pots.items() if value is None or value <= 0]
    if bad:
        report.add(RED, "POT values", "missing or non-numeric POT for runs %s" % bad)
    # GENIE stores the generated POT as the gtree weight: pot_N.csv must match it.
    mismatch = []
    for run, path in ghep.items():
        handle = open_root(path)
        tree = handle.Get("gtree") if handle else None
        weight = tree.GetWeight() if tree else None
        if weight and pots.get(run) and abs(pots[run] / weight - 1) > 1e-5:
            mismatch.append((run, pots[run], weight))
        elif weight and run in pots and not pots[run]:
            mismatch.append((run, None, weight))
    report.add(RED if mismatch else GREEN, "POT vs gtree weight",
               ("pot_N.csv differs from the ghep gtree weight (run, csv, weight): %s" % mismatch[:5]) if mismatch
               else "pot_N.csv matches the gtree weight in every run")
    ref_pots = [read_pot(p) for p in glob.glob(os.path.join(a.ref_dir, "pot_*.csv"))]
    ref_pots = [p for p in ref_pots if p]
    good = [v for v in pots.values() if v]
    if good and ref_pots:
        compare(report, "POT per run", mean(good), mean(ref_pots), rel=0.10)
    test, ref = genie_stats(gst.values()), genie_stats(glob.glob(os.path.join(a.ref_dir, "gntp.*.gst.root")))
    if not test:
        report.add(RED, "gst content", "no readable gst trees")
        return
    t_ns = test["vtxt_median"] * 1e9
    report.add(RED if t_ns > 1000 else GREEN, "vertex time",
               "median %.1f ns%s" % (t_ns, " — microseconds: the 2026-07 ZMIN timing bug?" if t_ns > 1000 else ""))
    if not ref:
        report.add(YELLOW, "reference gst", "no reference gst files in %s" % a.ref_dir)
        return
    compare(report, "mean neutrino energy", test["ev"], ref["ev"], rel=0.05, unit=" GeV")
    compare(report, "CC fraction", test["cc"], ref["cc"], absolute=0.03)
    compare(report, "numu fraction", test["numu"], ref["numu"], absolute=0.03)
    compare(report, "vertex time median", t_ns, ref["vtxt_median"] * 1e9, rel=0.5, unit=" ns")
    for tgt, frac in sorted(ref["targets"].items(), key=lambda kv: -kv[1]):
        if frac >= 0.02:
            compare(report, "target %d fraction" % tgt, test["targets"].get(tgt, 0.0), frac, absolute=0.05)
    half = world_half_lengths(a.geometry)
    if a.volume == "world" and half:
        # Extremes grow with sample size, so compare with the geometry, not with the reference files.
        out = ["%s [%.2f, %.2f] m" % (ax, lo, hi) for ax, (lo, hi) in sorted(test["extent"].items())
               if lo < -half[ax] - 0.01 or hi > half[ax] + 0.01]
        report.add(RED if out else GREEN, "vertex extent",
                   ("outside the world volume: %s" % out) if out else "inside the world volume (±%.1f, ±%.1f, ±%.1f m)"
                   % (half["vtxx"], half["vtxy"], half["vtxz"]))


def check_anniedirt(report, a, runs):
    files = run_files(a.test_dir, "annie_tank_flux.{run}.root", runs)
    completeness(report, "anniedirt files", files, runs)
    completeness(report, "anniedirt logs", run_files(a.test_dir, "annie_tank_flux.{run}.log.gz", runs), runs,
                 required=False)
    counts, problems, pot_off = [], [], []
    for run, path in files.items():
        handle = open_root(path)
        if not handle or not {"tankflux", "tankmeta"} <= tree_names(handle):
            problems.append("run %d: tankflux/tankmeta missing" % run)
            continue
        counts.append(entries(handle, "tankflux"))
        meta = handle.Get("tankmeta")
        meta.GetEntry(0)
        n_in, n_g4 = int(meta.inputNEntries), int(meta.nG4Events)
        if n_g4 != n_in:
            problems.append("run %d: processed %d of %d GENIE events" % (run, n_g4, n_in))
        if n_in != a.events:
            report.add(YELLOW, "GENIE events in run %d" % run, "%d (expected %d)" % (n_in, a.events))
        source = as_text(meta.inputFluxName)
        if not source.endswith("gntp.%d.ghep.root" % run):
            report.add(YELLOW, "input of run %d" % run, "tankmeta says %s" % source)
        pot_csv = os.path.join(a.pot_dir or "", "pot_%d.csv" % run)
        if a.pot_dir and os.path.exists(pot_csv):
            genie_pot = read_pot(pot_csv)
            if genie_pot and abs(float(meta.inputTotalPOTs) / genie_pot - 1) > 0.05:
                pot_off.append(run)
    report.add(RED if problems else GREEN, "anniedirt content", "; ".join(problems[:5]) or "trees present, all events processed")
    if pot_off:
        report.add(YELLOW, "POT consistency", "tankmeta POT differs >5 %% from pot_N.csv for runs %s" % pot_off)
    if counts and min(counts) == 0:
        report.add(RED, "events per file", "some files have 0 events")
    elif counts and a.volume == "tank":
        report.add(YELLOW if mean(counts) < 0.5 * a.events else GREEN, "events per file",
                   "mean %.0f (tank: expect ~%d)" % (mean(counts), a.events))
    elif counts:
        refs = [entries(open_root(p), "tankflux") for p in glob.glob(os.path.join(a.ref_dir, "annie_tank_flux.*.root"))]
        compare(report, "events per file", mean(counts), mean([r for r in refs if r]) if any(refs) else None, rel=0.30)


def check_wcsim(report, a, runs):
    pmt = run_files(a.test_dir, "wcsim_{run}.root", runs)
    completeness(report, "WCSim PMT files", pmt, runs)
    if a.outputs == "both":
        lappd = run_files(a.test_dir, "wcsim_lappd_{run}.root", runs)
        completeness(report, "WCSim LAPPD files", lappd, runs)
        unreadable = [r for r, p in lappd.items() if not (open_root(p) and tree_names(open_root(p)))]
        if unreadable:
            report.add(RED, "LAPPD content", "no readable TTree in runs %s" % unreadable)
    completeness(report, "WCSim logs", run_files(a.test_dir, "wcsim_{run}.log.gz", runs), runs, required=False)
    counts, per_event, problems, mismatch = [], [], [], []
    for run, path in pmt.items():
        handle = open_root(path)
        if not handle or not {"wcsimT", "wcsimGeoT"} <= tree_names(handle):
            problems.append("run %d: wcsimT/wcsimGeoT missing" % run)
            continue
        n = entries(handle, "wcsimT")
        if not n:
            problems.append("run %d: 0 events" % run)
            continue
        counts.append(n)
        per_event.append(os.path.getsize(path) / float(n))
        dirt = os.path.join(a.dirt_dir or "", "annie_tank_flux.%d.root" % run)
        if a.dirt_dir and os.path.exists(dirt):
            n_dirt = entries(open_root(dirt), "tankflux")
            if n_dirt and not 0.9 <= n / float(n_dirt) <= 1.1:
                mismatch.append((run, n, n_dirt))
    report.add(RED if problems else GREEN, "WCSim content", "; ".join(problems[:5]) or "trees present, events > 0")
    if mismatch:
        report.add(YELLOW, "events vs anniedirt", "WCSim / dirt events differ >10 %% (run, wcsim, dirt): %s" % mismatch[:5])
    elif a.dirt_dir and counts:
        report.add(GREEN, "events vs anniedirt", "WCSim events match the anniedirt files (±10 %)")
    refs = [p for p in glob.glob(os.path.join(a.ref_dir, "wcsim_[0-9]*.root"))]
    ref_counts = [entries(open_root(p), "wcsimT") for p in refs]
    ref_bytes = [os.path.getsize(p) / float(n) for p, n in zip(refs, ref_counts) if n]
    if counts and a.volume == "world":
        compare(report, "events per file", mean(counts), mean([n for n in ref_counts if n]) if ref_bytes else None, rel=0.30)
    if per_event:
        compare(report, "bytes per event", mean(per_event), mean(ref_bytes) if ref_bytes else None, rel=0.40, unit=" B")


def check_toolchain(report, a, runs):
    files = run_files(a.test_dir, "MC_{run}.root", runs)
    completeness(report, "MC toolchain files", files, runs)
    refs = glob.glob(os.path.join(a.ref_dir, "MC_*.root"))
    ref_trees, ref_entries = set(), {}
    for path in refs:
        handle = open_root(path)
        if handle:
            for name in tree_names(handle):
                ref_trees.add(name)
                ref_entries.setdefault(name, []).append(entries(handle, name))
    test_trees, test_entries, unreadable, empty = set(), {}, [], []
    for run, path in files.items():
        handle = open_root(path)
        names = tree_names(handle) if handle else set()
        if not names:
            unreadable.append(run)
            continue
        test_trees |= names
        counts = {name: entries(handle, name) for name in names}
        if not any(counts.values()):        # ~1400 WCSim events per file: an all-empty file is never physics
            empty.append(run)
        for name, n in counts.items():
            test_entries.setdefault(name, []).append(n)
    if unreadable:
        report.add(RED, "MC file content", "unreadable or no TTrees: runs %s" % unreadable)
    if empty:
        report.add(RED, "MC file content", "no entries in any tree: runs %s. The tree maker never filled: check the "
                   "toolchain config script against the tools in ToolsConfig (e.g. PMTWaveformSim 1 without the "
                   "PMTWaveformSim tool)" % sorted(empty))
    for name in sorted(ref_trees - test_trees):
        report.add(YELLOW, "tree " + name, "CAUTION: present in the reference files but missing here — is that "
                   "expected? (analysers may not fill it by design)")
    for name in sorted(test_trees - ref_trees):
        report.add(GREEN, "extra tree " + name, "not in the reference files (informational)")
    for name in sorted(test_trees & ref_trees):
        compare(report, "entries " + name, mean(test_entries[name]), mean(ref_entries[name]), rel=0.40, caution=True)
    if not refs:
        report.add(YELLOW, "reference MC files", "none found in %s" % a.ref_dir)
    ratios = []
    for run, path in files.items():
        wcsim = os.path.join(a.wcsim_dir or "", "wcsim_%d.root" % run)
        handle = open_root(path)
        if a.wcsim_dir and handle and os.path.exists(wcsim) and "phaseIITriggerTree" in tree_names(handle):
            n_wcsim = entries(open_root(wcsim), "wcsimT")
            if n_wcsim:
                ratios.append(entries(handle, "phaseIITriggerTree") / float(n_wcsim))
    if ratios:
        report.add(GREEN, "triggers per WCSim event", "mean %.2f (informational)" % mean(ratios))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", required=True, choices=("genie", "anniedirt", "wcsim", "toolchain"))
    p.add_argument("--test-dir", required=True)
    p.add_argument("--ref-dir", required=True)
    p.add_argument("--runs", required=True, help="comma-separated test run numbers")
    p.add_argument("--json", help="write the result here")
    p.add_argument("--events", type=int, default=20000)
    p.add_argument("--volume", default="world")
    p.add_argument("--geometry", help="GDML file (world-volume check)")
    p.add_argument("--outputs", default="both")
    p.add_argument("--pot-dir")
    p.add_argument("--dirt-dir")
    p.add_argument("--wcsim-dir")
    a = p.parse_args()
    runs = [int(r) for r in a.runs.split(",") if r]
    report = Report(a.stage)
    if not os.path.isdir(a.ref_dir):
        report.add(YELLOW, "reference files", "reference_dir %s not found" % a.ref_dir)
    {"genie": check_genie, "anniedirt": check_anniedirt, "wcsim": check_wcsim,
     "toolchain": check_toolchain}[a.stage](report, a, runs)
    result = {"stage": a.stage, "verdict": report.verdict(), "checks": report.checks}
    for c in report.checks:
        print("%-6s %-28s %s" % (c["level"], c["name"], c["message"]))
    print("VERDICT %s" % result["verdict"])
    if a.json:
        with open(a.json, "w") as handle:
            json.dump(result, handle, indent=1)


if __name__ == "__main__":
    main()
