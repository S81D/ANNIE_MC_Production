"""Load, validate and resolve a production YAML file (all keys: docs/configuration.md)."""
import copy
import getpass
import hashlib
import os
import re

import yaml

from . import REPO, STAGES

IMAGES = "/cvmfs/singularity.opensciencegrid.org/anniesoft/"
SPLINE = ("/cvmfs/larsoft.opensciencegrid.org/products/genie_xsec/v3_00_04_ub2/NULL/"
          "G1810a0211a-k250-e1000/data/gxspl-FNALsmall.xml")


def _res(memory, disk, lifetime):
    return {"memory": memory, "disk": disk, "lifetime": lifetime}


# Every allowed key and its default; None means "must be set when the stage is used".
DEFAULTS = {
    "production": {"name": None, "user": None, "group": "annie"},
    "runs": {"range": None, "list": None},
    "seeds": {"mode": "deterministic"},
    "grid": {"site": "onsite", "offsite_blacklist": ["Omaha", "Swan", "Wisconsin", "SU-ITS", "RAL"],
             "auto_release": True, "grace_memory": "4000MB", "confirm_above": 10},
    "recovery": {"complete_fraction": 0.95},
    "test": {"n_jobs": 10, "runs": None, "memory_step": "2000MB",
             "margins": {"memory": 1.25, "disk": 1.5, "walltime": 2.0}},
    "paths": {"scratch": "/pnfs/annie/scratch/users/{user}/ANNIE_MC_Production/{production}",
              "persistent": "/pnfs/annie/persistent/users/{user}/{production}",
              "flux_dir": "/pnfs/annie/persistent/users/jminock/flux",
              "geometry": "common/geometry/annie_v07.gdml",
              "container_tmp": "/exp/annie/app/users/{user}/temp_directory"},
    "validation": {"reference_dir": "/pnfs/annie/persistent/users/doran/PRODUCTION_MC_VALIDATION_FILES"},
    "layout": {
        "genie": {"ghep": "genie/ghep", "gst": "genie/gst", "logs": "genie/logs", "pot": "genie/POT",
                  "pot_summary": "genie/POT_summary.txt"},
        "anniedirt": {"root": "anniedirt/annie", "logs": "anniedirt/logs"},
        "wcsim": {"pmt": "wcsim/pmts", "lappd": "wcsim/lappd", "logs": "wcsim/logs"},
        "toolchain": {"root": "MC_toolchain/{version}", "logs": "MC_toolchain/{version}/logs",
                      "pot_summary": "MC_toolchain/{version}/POT_summary.txt"},
    },
    "transfer": {"method": "ifdh", "batch_size": 100},
    "genie": {"container": IMAGES + "genie3:latest", "software": "builtin", "tarball": None,
              "tarball_folder": None, "source_dir": None, "setup_script": "genie/worker/Setup_GENIE.sh",
              "spline": SPLINE, "tune": "G18_10a_02_11a", "volume": "world", "tank_topvol": "TWATER_LV",
              "events_per_job": 20000, "flux_file": "gsimple_flux_{index}.root", "flux_index_offset": 0,
              "verify_trees": ["gtree"], "resources": _res("4000MB", "10GB", "4h")},
    "anniedirt": {"container": IMAGES + "g4dirt:latest", "input": None, "events_per_job": 20000,
                  "verify_trees": ["tankflux", "tankmeta"], "resources": _res("4000MB", "10GB", "4h")},
    "wcsim": {"container": IMAGES + "wcsim:latest", "tarball": None, "source_dir": None,
              "genie_input": None, "dirt_input": None, "outputs": "both", "keep_logs": False,
              "keep_failed_logs": False, "verify_trees": ["wcsimT", "wcsimGeoT"],
              "resources": _res("4000MB", "5GB", "4h")},
    "toolchain": {"container": IMAGES + "toolanalysis:latest", "tarball": None, "source_dir": None,
                  "ta_folder": None, "toolchain": None, "version": "v1.0",
                  "config_hook": "toolchain/hooks/config_GENIE.py", "output_file": "tree.root",
                  "attach_lappd": False, "wcsim_input": None, "lappd_input": None, "genie_input": None,
                  "pot_input": None, "keep_logs": False, "keep_failed_logs": False,
                  "verify_trees": ["phaseIITriggerTree", "phaseIITankClusterTree", "phaseIIMRDClusterTree"],
                  "resources": _res("4000MB", "5GB", "4h")},
}

CHOICES = {("seeds", "mode"): ("deterministic", "random"), ("grid", "site"): ("onsite", "offsite"),
           ("transfer", "method"): ("ifdh", "cp"), ("genie", "software"): ("builtin", "tarball"),
           ("genie", "volume"): ("world", "tank"), ("wcsim", "outputs"): ("both", "pmt")}
PATH_KEYS = {"paths": ("scratch", "persistent", "flux_dir", "geometry", "container_tmp"),
             "validation": ("reference_dir",),
             "genie": ("tarball", "source_dir", "setup_script"), "anniedirt": ("input",),
             "wcsim": ("tarball", "source_dir", "genie_input", "dirt_input"),
             "toolchain": ("tarball", "source_dir", "config_hook", "wcsim_input", "lappd_input",
                           "genie_input", "pot_input")}
REPO_RELATIVE = {("paths", "geometry"), ("genie", "setup_script"), ("toolchain", "config_hook")}


class ConfigError(Exception):
    pass


def _merge(defaults, given, where):
    out = copy.deepcopy(defaults)
    for key, value in given.items():
        if key not in defaults:
            raise ConfigError("unknown key '%s%s'" % (where, key))
        if isinstance(defaults[key], dict):
            if not isinstance(value, dict):
                raise ConfigError("'%s%s' must be a mapping" % (where, key))
            out[key] = _merge(defaults[key], value, where + key + ".")
        else:
            out[key] = value
    return out


def parse_mb(text):
    """'4000MB' or '4GB' -> MB (int)."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(MB|GB)\s*", str(text), re.I)
    if not m:
        raise ConfigError("bad memory value '%s' (use e.g. 4000MB)" % text)
    value = float(m.group(1)) * (1000 if m.group(2).upper() == "GB" else 1)
    return int(round(value))


def parse_gb(text):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*GB\s*", str(text), re.I)
    if not m:
        raise ConfigError("bad disk value '%s' (use e.g. 10GB)" % text)
    return float(m.group(1))


def parse_hours(text):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(h|m)\s*", str(text), re.I)
    if not m:
        raise ConfigError("bad lifetime value '%s' (use e.g. 4h)" % text)
    return float(m.group(1)) / (60.0 if m.group(2).lower() == "m" else 1.0)


def _fmt(text, values, where):
    try:
        return text.format(**values)
    except KeyError as err:
        raise ConfigError("unknown placeholder {%s} in %s" % (err.args[0], where))


def load(path):
    with open(path) as handle:
        try:
            given = yaml.safe_load(handle) or {}
        except yaml.YAMLError as err:
            raise ConfigError("%s is not valid YAML (quote values that contain {placeholders} inside {...} mappings):\n%s" % (path, err))
    if not isinstance(given, dict):
        raise ConfigError("%s: top level must be a mapping" % path)
    cfg = _merge(DEFAULTS, given, "")
    cfg["_file"] = os.path.abspath(path)
    with open(path, "rb") as handle:
        cfg["_sha"] = hashlib.sha1(handle.read()).hexdigest()[:12]
    _validate(cfg)
    _resolve(cfg)
    return cfg


def _validate(cfg):
    name = cfg["production"]["name"]
    if not name or not re.fullmatch(r"[A-Za-z0-9_.-]+", str(name)):
        raise ConfigError("production.name is required (letters, digits, _ . - only)")
    for (section, key), allowed in CHOICES.items():
        if cfg[section][key] not in allowed:
            raise ConfigError("%s.%s must be one of %s" % (section, key, ", ".join(allowed)))
    runs = cfg["runs"]
    if runs["list"] is None and runs["range"] is None:
        raise ConfigError("set runs.range [first, last] or runs.list")
    if runs["list"] is not None and not all(isinstance(r, int) and r >= 0 for r in runs["list"]):
        raise ConfigError("runs.list must contain non-negative integers")
    if runs["range"] is not None:
        rng = runs["range"]
        if not (isinstance(rng, list) and len(rng) == 2 and all(isinstance(r, int) for r in rng)
                and 0 <= rng[0] <= rng[1]):
            raise ConfigError("runs.range must be [first, last] with 0 <= first <= last")
    for stage in STAGES:
        res = cfg[stage]["resources"]
        parse_mb(res["memory"]), parse_gb(res["disk"]), parse_hours(res["lifetime"])
    if cfg["grid"]["grace_memory"]:
        parse_mb(cfg["grid"]["grace_memory"])
    parse_mb(cfg["test"]["memory_step"])


def _resolve(cfg):
    user = cfg["production"]["user"] or os.environ.get("USER") or getpass.getuser()
    cfg["production"]["user"] = user
    values = {"user": user, "production": cfg["production"]["name"],
              "version": cfg["toolchain"]["version"]}
    for section, keys in PATH_KEYS.items():
        for key in keys:
            value = cfg[section][key]
            if value is None:
                continue
            value = _fmt(str(value), values, "%s.%s" % (section, key))
            if (section, key) in REPO_RELATIVE and not os.path.isabs(value):
                value = os.path.join(REPO, value)
            cfg[section][key] = value
    for stage, subdirs in cfg["layout"].items():
        for key, value in subdirs.items():
            subdirs[key] = os.path.join(cfg["paths"]["persistent"], _fmt(value, values, "layout." + stage))


def runs(cfg):
    if cfg["runs"]["list"] is not None:
        return sorted(set(cfg["runs"]["list"]))
    first, last = cfg["runs"]["range"]
    return list(range(first, last + 1))


def test_runs(cfg):
    if cfg["test"]["runs"]:
        return sorted(set(cfg["test"]["runs"]))
    return runs(cfg)[:cfg["test"]["n_jobs"]]


def require(cfg, stage, *keys):
    missing = [k for k in keys if cfg[stage][k] in (None, "")]
    if missing:
        raise ConfigError("%s: set %s" % (stage, ", ".join("%s.%s" % (stage, k) for k in missing)))
