"""Suggest resource requests from the test jobs' manifests."""
import glob
import json
import math
import os

from . import stages
from .config import parse_mb


def load_manifests(cfg, stage):
    found = []
    for path in glob.glob(os.path.join(stages.scratch_dir(cfg, stage, True), "*_manifest.json")):
        with open(path) as handle:
            try:
                found.append(json.load(handle))
            except ValueError:
                pass
    return found


def suggest(cfg, peaks):
    """peaks: list of (rss_mb, disk_mb, wall_s). Memory in memory_step multiples, disk GB, walltime hours."""
    m, step = cfg["test"]["margins"], parse_mb(cfg["test"]["memory_step"])
    rss = max(p[0] for p in peaks)
    disk_gb = max(p[1] for p in peaks) / 1024.0
    wall_h = max(p[2] for p in peaks) / 3600.0
    return {"memory": "%dMB" % (step * max(1, math.ceil(m["memory"] * rss / step))),
            "disk": "%dGB" % max(1, math.ceil(m["disk"] * disk_gb)),
            "lifetime": "%dh" % max(1, math.ceil(m["walltime"] * wall_h))}


def report(cfg, stage):
    manifests = [x for x in load_manifests(cfg, stage) if x.get("status") == "ok"]
    if not manifests:
        raise SystemExit("no successful test-job manifests in %s" % stages.scratch_dir(cfg, stage, True))
    lines = ["  %-6s %-22s %9s %9s %8s" % ("run", "site", "peak MB", "disk MB", "wall s")]
    peaks = []
    for x in sorted(manifests, key=lambda x: int(x["run"])):
        peaks.append((float(x["peak_rss_mb"]), float(x["peak_disk_mb"]), float(x["wall_s"])))
        lines.append("  %-6s %-22s %9.0f %9.0f %8.0f" % (x["run"], x.get("site", "?")[:22], *peaks[-1]))
    rss = [p[0] for p in peaks]
    if max(rss) > 1.5 * min(rss) and max(rss) > 500:
        lines.append("  note: peak memory varies a lot between jobs — consider more test runs")
    suggestion = suggest(cfg, peaks)
    current = cfg[stage]["resources"]
    lines.append("  current:   memory %s, disk %s, lifetime %s" % (current["memory"], current["disk"], current["lifetime"]))
    lines.append("  suggested (paste into %s.resources):" % stage)
    lines.append("    resources: {memory: %s, disk: %s, lifetime: %s}" % (
        suggestion["memory"], suggestion["disk"], suggestion["lifetime"]))
    return suggestion, lines
