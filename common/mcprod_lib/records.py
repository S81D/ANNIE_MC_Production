"""Local bookkeeping in <repo>/records/<production>/: campaigns, per-job submissions, stage state, mcprod.log."""
import datetime
import json
import os
import random
import sys

from . import REPO, STAGES
from .stages import PREVIOUS

_LOG = None


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def base_dir(cfg):
    root = os.environ.get("MCPROD_RECORDS") or os.path.join(REPO, "records")   # override: tests
    return os.path.join(root, cfg["production"]["name"])


def stage_dir(cfg, stage, test=False):
    path = os.path.join(base_dir(cfg), "test", stage) if test else os.path.join(base_dir(cfg), stage)
    os.makedirs(path, exist_ok=True)
    return path


def open_log(cfg):
    """Echo everything mcprod prints to records/<production>/mcprod.log (useful from a detached screen)."""
    global _LOG
    os.makedirs(base_dir(cfg), exist_ok=True)
    _LOG = open(os.path.join(base_dir(cfg), "mcprod.log"), "a")
    _LOG.write("\n=== %s  %s\n" % (now(), " ".join(sys.argv)))


def say(*parts):
    text = " ".join(str(p) for p in parts)
    print(text, flush=True)
    if _LOG:
        _LOG.write(text + "\n")
        _LOG.flush()


# ---- campaigns -----------------------------------------------------------------------------------

def campaigns(cfg, stage, test=False):
    path = os.path.join(stage_dir(cfg, stage, test), "campaigns.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def next_kind(cfg, stage, test, missing):
    prefix = "test " if test else ""
    previous = campaigns(cfg, stage, test)
    if not previous:
        return prefix + "initial"
    if missing:
        n = sum(1 for c in previous if "recovery" in c["kind"]) + 1
        return prefix + "recovery %d" % n
    return prefix + "rerun"


def start_campaign(cfg, stage, test, kind, runs, n_expected, n_done_before, commit):
    camp = {"id": datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "kind": kind, "started": now(),
            "runs": runs, "n_expected": n_expected, "n_done_before": n_done_before,
            "commit": commit, "config_sha": cfg["_sha"]}
    camp["jobs_file"] = os.path.join(stage_dir(cfg, stage, test), "jobs_%s.jsonl" % camp["id"])
    return camp


def record_job(camp, entry):
    with open(camp["jobs_file"], "a") as handle:
        handle.write(json.dumps(entry) + "\n")


def finish_campaign(cfg, stage, test, camp, n_submitted, n_failed):
    camp.update(finished=now(), n_submitted=n_submitted, n_submit_failed=n_failed)
    with open(os.path.join(stage_dir(cfg, stage, test), "campaigns.jsonl"), "a") as handle:
        handle.write(json.dumps(camp) + "\n")


def jobs(camp):
    if not os.path.exists(camp["jobs_file"]):
        return []
    with open(camp["jobs_file"]) as handle:
        return [json.loads(line) for line in handle if line.strip()]


# ---- stage state (validate / verify / copy results) -------------------------------------------------

def state(cfg, stage, test=False):
    path = os.path.join(stage_dir(cfg, stage, test), "state.json")
    if not os.path.exists(path):
        return {}
    with open(path) as handle:
        return json.load(handle)


def set_state(cfg, stage, test, key, value):
    current = state(cfg, stage, test)
    current[key] = value
    with open(os.path.join(stage_dir(cfg, stage, test), "state.json"), "w") as handle:
        json.dump(current, handle, indent=1)


# ---- seeds ---------------------------------------------------------------------------------------

def used_seeds(cfg, stage, test):
    seen = set()
    for camp in campaigns(cfg, stage, test):
        seen.update(j["seed"] for j in jobs(camp) if "seed" in j)
    return seen


def make_seeds(cfg, stage, runs, test):
    """deterministic: GENIE = run (unchanged), other stages = run + 1. random: unique 1 <= s < 2**31."""
    if cfg["seeds"]["mode"] == "deterministic":
        offset = 0 if stage == "genie" else 1
        return {run: run + offset for run in runs}
    rng, used, seeds = random.SystemRandom(), used_seeds(cfg, stage, test), {}
    for run in runs:
        seed = rng.randint(1, 2 ** 31 - 1)
        while seed in used:
            seed = rng.randint(1, 2 ** 31 - 1)
        used.add(seed)
        seeds[run] = seed
    return seeds


# ---- stage gate ------------------------------------------------------------------------------------

def stage_done(cfg, stage, test):
    """(done?, reason). Test DONE = validated GREEN or accepted YELLOW. Full DONE = copied to persistent."""
    st = state(cfg, stage, test)
    if test:
        val = st.get("validate")
        if not val:
            return False, "test %s not validated yet (./mcprod validate ... %s)" % (stage, stage)
        if val["verdict"] == "GREEN" or (val["verdict"] == "YELLOW" and val.get("accepted")):
            return True, ""
        return False, "test %s validation is %s%s" % (stage, val["verdict"],
                                                      " (review, then --accept)" if val["verdict"] == "YELLOW" else "")
    if not st.get("copy", {}).get("completed"):
        return False, "%s is not copied to persistent yet (./mcprod copy ... %s)" % (stage, stage)
    return True, ""


def gate(cfg, stage, test):
    """Problems that block submitting this stage (empty list = OK to go)."""
    problems = []
    prev = PREVIOUS[stage]
    if prev:
        ok, why = stage_done(cfg, prev, test)
        if not ok:
            problems.append("previous stage not DONE: " + why)
    if not test:
        ok, why = stage_done(cfg, stage, True)
        if not ok:
            problems.append("this stage's test is not DONE: " + why)
    return problems


def chain_test_done(cfg):
    return all(stage_done(cfg, s, True)[0] for s in STAGES)
