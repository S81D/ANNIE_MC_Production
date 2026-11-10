"""What each stage reads, writes and ships to the worker."""
import os
import re

from . import REPO, STAGES

PREVIOUS = {"genie": None, "anniedirt": "genie", "wcsim": "anniedirt", "toolchain": "wcsim"}

# Output file kinds per stage: kind -> (file name template, persistent layout key, required for "done").
OUTPUTS = {
    "genie": {"ghep": ("gntp.{run}.ghep.root", "ghep", True),
              "gst": ("gntp.{run}.gst.root", "gst", True),
              "pot": ("pot_{run}.csv", "pot", True),
              "log": ("gntp.{run}.ghep.log.gz", "logs", False),
              "maxpl": ("ANNIE-{run}.maxpl.xml", "logs", False),
              "flux": ("BNBFlux{run}.xml", "logs", False)},
    "anniedirt": {"root": ("annie_tank_flux.{run}.root", "root", True),
                  "log": ("annie_tank_flux.{run}.log.gz", "logs", False)},
    "wcsim": {"pmt": ("wcsim_{run}.root", "pmt", True),
              "lappd": ("wcsim_lappd_{run}.root", "lappd", True),
              "log": ("wcsim_{run}.log.gz", "logs", False)},
    "toolchain": {"root": ("MC_{run}.root", "root", True),
                  "log": ("toolchain_{run}.log.gz", "logs", False)},
}
MANIFEST = "{run}_{jobid}_manifest.json"
DUMMY = "{run}_{jobid}_dummy_output"
# Rough output size per run in MB (from the 4000-run productions), for the data-volume line before submitting.
MB_PER_RUN = {"genie": 25.0, "anniedirt": 0.5, "wcsim": 29.0, "wcsim_lappd": 14.0, "toolchain": 30.0}
VERIFY_PATTERN = {"genie": "gntp.*.ghep.root", "anniedirt": "annie_tank_flux.*.root",
                  "wcsim": "wcsim_[0-9]*.root", "toolchain": "MC_*.root"}


def outputs(cfg, stage):
    """Output kinds in use for this stage (WCSim LAPPD only with outputs: both)."""
    kinds = dict(OUTPUTS[stage])
    if stage == "wcsim" and cfg["wcsim"]["outputs"] == "pmt":
        kinds.pop("lappd")
    return kinds


def output_regex(template):
    """'gntp.{run}.ghep.root' -> compiled regex capturing the run number."""
    return re.compile("^" + re.escape(template).replace(re.escape("{run}"), r"(\d+)") + "$")


def scratch_dir(cfg, stage, test=False):
    return os.path.join(cfg["paths"]["scratch"], "test", stage) if test else \
        os.path.join(cfg["paths"]["scratch"], stage)


def _default_input(cfg, stage, layout_key, test):
    return scratch_dir(cfg, stage, True) if test else cfg["layout"][stage][layout_key]


def input_dirs(cfg, stage, test=False):
    """Directory of every per-run input: label -> (dir, file template). Explicit config overrides win."""
    if stage == "genie":
        return {"flux": (cfg["paths"]["flux_dir"], None)}
    if stage == "anniedirt":
        return {"ghep": (cfg["anniedirt"]["input"] or _default_input(cfg, "genie", "ghep", test),
                         "gntp.{run}.ghep.root")}
    if stage == "wcsim":
        c = cfg["wcsim"]
        return {"ghep": (c["genie_input"] or _default_input(cfg, "genie", "ghep", test), "gntp.{run}.ghep.root"),
                "dirt": (c["dirt_input"] or _default_input(cfg, "anniedirt", "root", test),
                         "annie_tank_flux.{run}.root")}
    c = cfg["toolchain"]
    dirs = {"wcsim": (c["wcsim_input"] or _default_input(cfg, "wcsim", "pmt", test), "wcsim_{run}.root"),
            "ghep": (c["genie_input"] or _default_input(cfg, "genie", "ghep", test), "gntp.{run}.ghep.root")}
    if c["attach_lappd"]:
        dirs["lappd"] = (c["lappd_input"] or _default_input(cfg, "wcsim", "lappd", test), "wcsim_lappd_{run}.root")
    return dirs


def flux_index(cfg, run):
    return run - cfg["genie"]["flux_index_offset"]


def run_inputs(cfg, stage, run, test=False):
    """Full paths of the per-run input files (all must exist)."""
    paths = []
    for label, (directory, template) in input_dirs(cfg, stage, test).items():
        if stage == "genie":
            name = cfg["genie"]["flux_file"].format(index=flux_index(cfg, run))
        else:
            name = template.format(run=run)
        paths.append(os.path.join(directory, name))
    return paths


def static_files(cfg, stage):
    """Repo files shipped with every job (staged to pnfs) and pnfs files attached as they are."""
    staged = [os.path.join(REPO, "common/worker/job_common.sh"),
              os.path.join(REPO, stage, "worker", stage + "_container.sh")]
    attached = []
    if stage == "genie":
        staged += [os.path.join(REPO, "genie/worker/run_annie_genie.sh"), cfg["paths"]["geometry"]]
        if cfg["genie"]["software"] == "tarball":
            staged.append(cfg["genie"]["setup_script"])
            attached.append(cfg["genie"]["tarball"])
    elif stage == "anniedirt":
        staged += [cfg["paths"]["geometry"], os.path.join(REPO, "common/geometry/gdml_schema.tar.gz")]
    elif stage == "wcsim":
        attached.append(cfg["wcsim"]["tarball"])
    elif stage == "toolchain":
        attached.append(cfg["toolchain"]["tarball"])
        if cfg["toolchain"]["config_hook"]:
            staged.append(cfg["toolchain"]["config_hook"])
    return staged, attached


def executable(stage):
    return os.path.join(REPO, stage, "worker", stage + "_job.sh")


def job_args(cfg, stage, run, seed, test, commit):
    """key=value arguments for the worker (read by mc_parse_args in job_common.sh)."""
    c = cfg[stage]
    keep_logs = 1 if (test or c.get("keep_logs", True)) else 0
    keep_failed = 1 if (test or c.get("keep_failed_logs", True)) else 0
    args = {"production": cfg["production"]["name"], "stage": stage, "run": run, "test": int(bool(test)),
            "seed": seed, "container": c["container"], "keep_logs": keep_logs,
            "keep_failed_logs": keep_failed, "commit": commit, "config_sha": cfg["_sha"]}
    if stage == "genie":
        args.update(events=c["events_per_job"], software=c["software"], tune=c["tune"], volume=c["volume"],
                    tank_topvol=c["tank_topvol"], geometry=os.path.basename(cfg["paths"]["geometry"]),
                    flux_file=c["flux_file"].format(index=flux_index(cfg, run)),
                    spline=c["spline"])
        if c["software"] == "tarball":
            args.update(tarball=os.path.basename(c["tarball"]), tarball_folder=c["tarball_folder"])
    elif stage == "anniedirt":
        args.update(events=c["events_per_job"], geometry=os.path.basename(cfg["paths"]["geometry"]))
    elif stage == "wcsim":
        args.update(tarball=os.path.basename(c["tarball"]), outputs=c["outputs"])
    elif stage == "toolchain":
        args.update(tarball=os.path.basename(c["tarball"]), ta_folder=c["ta_folder"], toolchain=c["toolchain"],
                    output_file=c["output_file"], attach_lappd=int(bool(c["attach_lappd"])),
                    hook=os.path.basename(c["config_hook"]) if c["config_hook"] else "")
    return args


def required_config(cfg, stage):
    """Keys that must be set before this stage can be submitted."""
    needed = {"wcsim": ("tarball",), "toolchain": ("tarball", "ta_folder", "toolchain")}.get(stage, ())
    if stage == "genie" and cfg["genie"]["software"] == "tarball":
        needed = ("tarball", "tarball_folder")
    return needed


def check_stage(stage):
    if stage not in STAGES:
        raise SystemExit("unknown stage '%s' (choose from %s)" % (stage, ", ".join(STAGES)))
