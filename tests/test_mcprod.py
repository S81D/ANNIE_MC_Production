"""Unit tests for the submission side. Run from the repo root: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "common"))

from mcprod_lib import config, estimate, grid, records, stages, status, transfer  # noqa: E402
from mcprod_lib import cli  # noqa: E402


def touch(path, size=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x" * size)


class Fixture(unittest.TestCase):
    """A production whose pnfs, CVMFS and records paths all live in a temp dir."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mcprod_test_")
        self.flux = os.path.join(self.tmp, "flux")
        for i in range(10):
            if i != 3:
                touch(os.path.join(self.flux, "gsimple_flux_%d.root" % i))
        for image in ("genie3", "g4dirt", "wcsim", "toolanalysis"):
            os.makedirs(os.path.join(self.tmp, "images", image + ":latest"))
        self.cfg = self.make_config()
        os.environ["MCPROD_RECORDS"] = os.path.join(self.tmp, "records")     # keep records/ out of the repo

    def tearDown(self):
        os.environ.pop("MCPROD_RECORDS", None)
        subprocess.run(["rm", "-rf", self.tmp])

    def make_config(self, extra=""):
        text = textwrap.dedent("""
            production: {name: unit_test, user: tester}
            runs: {range: [0, 9]}
            paths:
              scratch: %(t)s/scratch/{production}
              persistent: %(t)s/persistent/{production}
              flux_dir: %(t)s/flux
            genie: {container: %(t)s/images/genie3:latest}
            anniedirt: {container: %(t)s/images/g4dirt:latest}
            wcsim: {container: %(t)s/images/wcsim:latest, tarball: %(t)s/tar/WCSim.tar.gz}
            toolchain: {container: %(t)s/images/toolanalysis:latest, tarball: %(t)s/tar/TA.tar.gz,
                        ta_folder: TA, toolchain: PMTWaveformSim}
            """) % {"t": self.tmp} + extra
        path = os.path.join(self.tmp, "prod.yaml")
        with open(path, "w") as handle:
            handle.write(text)
        return config.load(path)


class ConfigTests(Fixture):
    def test_defaults_and_placeholders(self):
        c = self.cfg
        self.assertEqual(c["production"]["user"], "tester")
        self.assertTrue(c["paths"]["scratch"].endswith("/scratch/unit_test"))
        self.assertTrue(c["layout"]["toolchain"]["root"].endswith("/persistent/unit_test/MC_toolchain/v1.0"))
        self.assertEqual(c["grid"]["offsite_blacklist"], ["Omaha", "Swan", "Wisconsin", "SU-ITS", "RAL"])
        self.assertTrue(c["paths"]["geometry"].endswith("common/geometry/annie_v07.gdml"))
        self.assertTrue(os.path.exists(c["paths"]["geometry"]))
        self.assertEqual(config.runs(c), list(range(10)))
        self.assertEqual(config.test_runs(c), list(range(10)))

    def test_unknown_key_and_bad_choice(self):
        with self.assertRaises(config.ConfigError):
            self.make_config("grid: {sight: onsite}\n")
        with self.assertRaises(config.ConfigError):
            self.make_config("seeds: {mode: sometimes}\n")
        with self.assertRaises(config.ConfigError):
            self.make_config("genie: {resources: {memory: lots, disk: 10GB, lifetime: 4h}}\n")

    def test_user_from_environment(self):
        os.environ["USER"] = "envuser"
        path = os.path.join(self.tmp, "u.yaml")
        with open(path, "w") as handle:
            handle.write("production: {name: x}\nruns: {list: [5, 2, 5]}\n")
        c = config.load(path)
        self.assertEqual(c["production"]["user"], "envuser")
        self.assertIn("/users/envuser/", c["paths"]["scratch"])
        self.assertEqual(config.runs(c), [2, 5])

    def test_parsers(self):
        self.assertEqual(config.parse_mb("4000MB"), 4000)
        self.assertEqual(config.parse_mb("4GB"), 4000)
        self.assertEqual(config.parse_gb("10GB"), 10.0)
        self.assertEqual(config.parse_hours("90m"), 1.5)


class SeedTests(Fixture):
    def test_deterministic(self):
        self.assertEqual(records.make_seeds(self.cfg, "genie", [0, 7], False), {0: 0, 7: 7})
        self.assertEqual(records.make_seeds(self.cfg, "wcsim", [0, 7], False), {0: 1, 7: 8})

    def test_random_unique_and_in_range(self):
        cfg = self.make_config("seeds: {mode: random}\n")
        seeds = records.make_seeds(cfg, "anniedirt", list(range(2000)), False)
        self.assertEqual(len(set(seeds.values())), 2000)
        self.assertTrue(all(1 <= s < 2 ** 31 for s in seeds.values()))


class StageTests(Fixture):
    def test_inputs_follow_previous_stage(self):
        c = self.cfg
        self.assertEqual(stages.input_dirs(c, "anniedirt")["ghep"][0], c["layout"]["genie"]["ghep"])
        self.assertEqual(stages.input_dirs(c, "anniedirt", True)["ghep"][0], stages.scratch_dir(c, "genie", True))
        c2 = self.make_config("wcsim: {genie_input: /official/ghep}\n")
        self.assertEqual(stages.input_dirs(c2, "wcsim", True)["ghep"][0], "/official/ghep")   # explicit wins in tests too
        self.assertNotIn("lappd", stages.input_dirs(c, "toolchain"))

    def test_flux_index_offset(self):
        c = self.make_config("genie: {flux_index_offset: 100000, container: %s/images/genie3:latest}\n" % self.tmp)
        self.assertTrue(stages.run_inputs(c, "genie", 100007)[0].endswith("gsimple_flux_7.root"))

    def test_local_genie_files_only_for_tarball(self):
        staged, attached = stages.static_files(self.cfg, "genie")
        self.assertFalse(any("Setup_GENIE" in p for p in staged))
        self.assertEqual(attached, [])
        c = self.make_config("genie: {software: tarball, tarball: /t/G.tar.gz, tarball_folder: G, "
                             "container: %s/images/genie3:latest}\n" % self.tmp)
        staged, attached = stages.static_files(c, "genie")
        self.assertTrue(any(p.endswith("Setup_GENIE.sh") for p in staged))
        self.assertEqual(attached, ["/t/G.tar.gz"])

    def toolchain_config(self, hook):
        return self.make_config("toolchain: {container: %s/images/toolanalysis:latest, tarball: /t/TA.tar.gz, "
                                "ta_folder: TA, toolchain: TC, config_hook: %s}\n" % (self.tmp, hook))

    def test_toolchain_config_script_modes(self):
        staged, _ = stages.static_files(self.cfg, "toolchain")
        self.assertIn(os.path.join(REPO, "toolchain/hooks/config_GENIE.py"), staged)
        self.assertEqual(stages.job_args(self.cfg, "toolchain", 1, 2, False, "abc")["hook"], "config_GENIE.py")
        nc = self.toolchain_config("toolchain/hooks/config_GENIE_NC.py")
        self.assertIn(os.path.join(REPO, "toolchain/hooks/config_GENIE_NC.py"), stages.static_files(nc, "toolchain")[0])
        own = self.toolchain_config("tarball")
        self.assertEqual(own["toolchain"]["config_hook"], "tarball")
        self.assertFalse(any("config_GENIE" in p for p in stages.static_files(own, "toolchain")[0]))
        self.assertEqual(stages.job_args(own, "toolchain", 1, 2, False, "abc")["hook"], "tarball")
        with self.assertRaises(config.ConfigError):
            self.toolchain_config("null")

    def test_log_policy_args(self):
        genie = stages.job_args(self.cfg, "genie", 1, 1, False, "abc")
        wcsim = stages.job_args(self.cfg, "wcsim", 1, 2, False, "abc")
        wcsim_test = stages.job_args(self.cfg, "wcsim", 1, 2, True, "abc")
        self.assertEqual((genie["keep_logs"], wcsim["keep_logs"], wcsim["keep_failed_logs"]), (1, 0, 0))
        self.assertEqual((wcsim_test["keep_logs"], wcsim_test["keep_failed_logs"]), (1, 1))

    def test_lappd_output_optional(self):
        self.assertIn("lappd", stages.outputs(self.cfg, "wcsim"))
        self.assertNotIn("lappd", stages.outputs(self.make_config("wcsim: {outputs: pmt, tarball: /x}\n"), "wcsim"))


class SubmitCommandTests(Fixture):
    def argv(self, cfg, no_submit=False):
        staged, attached = stages.static_files(cfg, "genie")
        args = stages.job_args(cfg, "genie", 5, 5, False, "abc")
        return grid.submit_argv(cfg, "genie", staged + attached + stages.run_inputs(cfg, "genie", 5), "/out",
                                "/in/genie_job.sh", args, no_submit)

    def test_no_submit_before_executable(self):
        argv = self.argv(self.cfg, no_submit=True)
        exe = [i for i, a in enumerate(argv) if a.startswith("file://")][0]
        self.assertEqual(argv.index("--no_submit"), exe - 1)

    def test_matches_old_genie_command_except_intended_changes(self):
        # Old submit_GENIE_jobs.sh (onsite, 4000 MB, 10 GB, 4 h):
        old = ["jobsub_submit", "--memory=4000MB", "--expected-lifetime=4h", "-G", "annie", "--disk=10GB",
               "--resource-provides=usage_model=DEDICATED,OPPORTUNISTIC"]
        new = self.argv(self.cfg)
        self.assertEqual(set(old), set(new[:len(old)]))
        self.assertIn("--lines=+FERMIHTC_AutoRelease=True", new)
        self.assertIn("--lines=+FERMIHTC_GraceMemory=4000", new)
        files = [new[i + 1] for i, a in enumerate(new) if a == "-f"]
        names = sorted(os.path.basename(f) for f in files)
        self.assertEqual(names, sorted(["job_common.sh", "genie_container.sh", "run_annie_genie.sh",
                                        "annie_v07.gdml", "gsimple_flux_5.root"]))   # spline now read from CVMFS
        self.assertIn("spline=" + config.SPLINE, new)
        self.assertIn("seed=5", new)

    def test_offsite_blacklist(self):
        new = self.argv(self.make_config("grid: {site: offsite}\n"))
        self.assertIn("--resource-provides=usage_model=OFFSITE", new)
        self.assertIn("--blacklist=Omaha,Swan,Wisconsin,SU-ITS,RAL", new)

    def test_queue_parsing(self):
        line = "\t".join(["1.0@jobsub01.fnal.gov", "5", "0", "4000", "0", "0",
                          "production=unit_test stage=wcsim run=12 test=0 seed=13", "", "tester", "tester", "0", "0"])
        fields = line.split("\t")
        self.assertEqual(grid.parse_args(fields[6])["run"], "12")


class StatusTests(Fixture):
    def make_genie_outputs(self, runs, directory=None, partial=()):
        d = directory or stages.scratch_dir(self.cfg, "genie")
        for r in runs:
            for kind in ("gntp.%d.ghep.root", "gntp.%d.gst.root", "pot_%d.csv"):
                touch(os.path.join(d, kind % r))
        for r in partial:
            touch(os.path.join(d, "gntp.%d.ghep.root" % r))

    def test_expected_done_missing(self):
        self.make_genie_outputs([0, 1, 2], partial=[4])
        self.make_genie_outputs([5], directory=self.cfg["layout"]["genie"]["ghep"])  # only ghep in persistent
        for kind, key in (("gntp.5.gst.root", "gst"), ("pot_5.csv", "pot")):
            touch(os.path.join(self.cfg["layout"]["genie"][key], kind))
        summary, lines = status.report(self.cfg, "genie", False)
        self.assertEqual(summary["expected"], 9)                # flux 3 missing
        self.assertEqual(summary["done_runs"], {0, 1, 2, 5})
        self.assertEqual(summary["missing"], [4, 6, 7, 8, 9])
        self.assertTrue(lines[-1].endswith("submit prod.yaml genie"))        # no campaign yet: plain submit

    def test_campaign_gain_and_95_percent(self):
        self.make_genie_outputs([0, 1, 2, 4, 5, 6, 7, 8, 9])
        camp = records.start_campaign(self.cfg, "genie", False, "initial", list(range(10)), 9, 0, "abc")
        for r in range(10):
            records.record_job(camp, {"run": r, "seed": r, "jobid": "%d.0@jobsub01.fnal.gov" % r})
        records.finish_campaign(self.cfg, "genie", False, camp, 10, 0)
        summary, lines = status.report(self.cfg, "genie", False)
        self.assertAlmostEqual(summary["fraction"], 1.0)
        self.assertTrue(any("DONE-level" in l for l in lines))
        self.assertEqual(status.campaign_table(self.cfg, "genie", False, summary["done_runs"])[0][3:], (9, 9))
        self.assertEqual(records.next_kind(self.cfg, "genie", False, True), "recovery 1")

    def add_campaign(self, kind, runs, n_done_before, **extra):
        camp = records.start_campaign(self.cfg, "genie", False, kind, runs, 9, n_done_before, "abc")
        camp["jobs_file"] = camp["jobs_file"].replace(".jsonl", "_%s.jsonl" % kind.replace(" ", "_"))  # same-second ids
        camp.update(extra)
        for r in runs:
            records.record_job(camp, {"run": r, "seed": r, "jobid": "%d.0@jobsub01.fnal.gov" % r})
        records.finish_campaign(self.cfg, "genie", False, camp, len(runs), 0)

    def test_campaign_credit_goes_to_last_submitter(self):
        runs = [0, 1, 2, 4, 5, 6, 7, 8, 9]
        self.make_genie_outputs(runs)
        self.add_campaign("initial", runs, 0)                 # run 9 failed here ...
        self.add_campaign("recovery 1", [9], 8)               # ... and was rescued here
        summary, _ = status.report(self.cfg, "genie", False)
        table = status.campaign_table(self.cfg, "genie", False, summary["done_runs"])
        self.assertEqual([row[3:] for row in table], [(8, 8), (9, 1)])

    def test_rerun_after_clear_scratch(self):
        runs = [0, 1, 2, 4, 5, 6, 7, 8, 9]
        self.make_genie_outputs(runs)
        self.add_campaign("initial", runs, 0)
        self.add_campaign("rerun", runs, 0, cleared=27)      # the initial campaign's files were deleted first
        summary, lines = status.report(self.cfg, "genie", False)
        table = status.campaign_table(self.cfg, "genie", False, summary["done_runs"])
        self.assertEqual([row[3:] for row in table], [(0, 0), (9, 9)])
        self.assertTrue(any("deleted 27 earlier scratch file(s)" in l for l in lines))

    def test_dry_run_never_clears_scratch(self):
        d = stages.scratch_dir(self.cfg, "genie", True)
        self.make_genie_outputs([0, 1], directory=d)
        before = sorted(os.listdir(d))
        rc = cli.main(["submit", self.cfg["_file"], "genie", "--test", "--dry-run", "--clear-scratch"])
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(os.listdir(d)), before)

    def test_failure_mix_reads_dummy(self):
        d = stages.scratch_dir(self.cfg, "genie")
        os.makedirs(d)
        with open(os.path.join(d, "7_1.0@jobsub01.fnal.gov_dummy_output"), "w") as handle:
            handle.write("...\nMCPROD_STATUS=failed exit=4 reason=missing_outputs:pot_7.csv\n")
        mix = status.failure_mix(self.cfg, "genie", False, {7, 8})
        self.assertEqual(sorted(len(v) for v in mix.values()), [1, 1])
        self.assertTrue(any(k.startswith("failed: exit 4") for k in mix))


class GateTests(Fixture):
    def test_gate_order(self):
        c = self.cfg
        self.assertEqual(records.gate(c, "genie", True), [])
        self.assertEqual(len(records.gate(c, "anniedirt", True)), 1)             # genie test not validated
        self.assertEqual(len(records.gate(c, "genie", False)), 1)                # own test not DONE
        records.set_state(c, "genie", True, "validate", {"verdict": "YELLOW"})
        self.assertEqual(len(records.gate(c, "anniedirt", True)), 1)             # YELLOW not accepted
        records.set_state(c, "genie", True, "validate", {"verdict": "YELLOW", "accepted": "now"})
        self.assertEqual(records.gate(c, "anniedirt", True), [])
        self.assertEqual(records.gate(c, "genie", False), [])
        records.set_state(c, "anniedirt", True, "validate", {"verdict": "GREEN"})
        self.assertEqual(len(records.gate(c, "anniedirt", False)), 1)            # genie not copied
        records.set_state(c, "genie", False, "copy", {"completed": "now"})
        self.assertEqual(records.gate(c, "anniedirt", False), [])


class EstimateTests(Fixture):
    def test_memory_steps(self):
        s = estimate.suggest(self.cfg, [(2100, 3000, 1800), (1500, 2000, 1200)])
        self.assertEqual(s, {"memory": "4000MB", "disk": "5GB", "lifetime": "1h"})
        self.assertEqual(estimate.suggest(self.cfg, [(1500, 500, 9000)])["memory"], "2000MB")
        self.assertEqual(estimate.suggest(self.cfg, [(1500, 500, 9000)])["lifetime"], "5h")


class TransferTests(Fixture):
    def test_plan_copies_done_runs_skips_present(self):
        d = stages.scratch_dir(self.cfg, "anniedirt")
        for r in (1, 2, 3):
            touch(os.path.join(d, "annie_tank_flux.%d.root" % r), 10)
            touch(os.path.join(d, "annie_tank_flux.%d.log.gz" % r), 5)
        touch(os.path.join(d, "1_9.0@jobsub01.fnal.gov_manifest.json"), 3)
        touch(os.path.join(self.cfg["layout"]["anniedirt"]["root"], "annie_tank_flux.2.root"), 10)   # already there
        touch(os.path.join(self.cfg["layout"]["anniedirt"]["root"], "annie_tank_flux.3.root"), 7)    # wrong size
        todo, present, conflicts = transfer.plan(self.cfg, "anniedirt", {1, 2, 3})
        names = sorted(os.path.basename(src) for src, _, _ in todo)
        self.assertEqual(names, ["1_9.0@jobsub01.fnal.gov_manifest.json", "annie_tank_flux.1.log.gz",
                                 "annie_tank_flux.1.root", "annie_tank_flux.2.log.gz", "annie_tank_flux.3.log.gz"])
        self.assertEqual(present, 1)
        self.assertEqual(len(conflicts), 1)
        self.cfg["transfer"]["method"] = "cp"
        self.assertEqual(transfer.copy(self.cfg, todo), [])
        self.assertTrue(os.path.exists(os.path.join(self.cfg["layout"]["anniedirt"]["logs"],
                                                    "1_9.0@jobsub01.fnal.gov_manifest.json")))


class PurgeGuardTests(Fixture):
    def test_refuses_paths_outside_scratch(self):
        listing = os.path.join(self.tmp, "broken.txt")
        with open(listing, "w") as handle:
            handle.write(self.cfg["layout"]["toolchain"]["root"] + "/MC_1.root\n")
        records.set_state(self.cfg, "toolchain", False, "verify", {"blocked": False, "fraction": 0.01, "list": listing})

        class A(object):
            stage, test, force, list = "toolchain", False, False, listing
        self.assertEqual(cli.cmd_purge(self.cfg, A()), 1)

    def test_blocked_when_too_many_flagged(self):
        records.set_state(self.cfg, "toolchain", False, "verify", {"blocked": True, "fraction": 0.2, "list": None})

        class A(object):
            stage, test, force, list = "toolchain", False, False, None
        self.assertEqual(cli.cmd_purge(self.cfg, A()), 1)


class TarballFingerprintTests(Fixture):
    def test_md5_cached_and_external_marked(self):
        from mcprod_lib import tarball
        path = os.path.join(self.tmp, "tar", "WCSim.tar.gz")
        touch(path, 1000)
        first = tarball.fingerprint(self.cfg, path)
        self.assertEqual(first["md5"], __import__("hashlib").md5(b"x" * 1000).hexdigest())
        self.assertTrue(first["built_by"].startswith("external"))
        self.assertEqual(tarball.fingerprint(self.cfg, path)["md5"], first["md5"])       # from the cache
        with open(path + ".provenance.json", "w") as handle:
            json.dump({"source": "/src/WCSim", "md5": "different", "git": {"commit": "abcdef1234567"}}, handle)
        built = tarball.fingerprint(self.cfg, path)["built_by"]
        self.assertIn("/src/WCSim @ abcdef1234", built)
        self.assertIn("WARNING", built)


class PotGuardTests(unittest.TestCase):
    def test_flags_missing_garbled_and_extra_digit(self):
        tmp = tempfile.mkdtemp()
        values = {1: "1.13e+17", 2: "1.12e+17", 3: "1.13339e+171", 4: "", 5: "1.11e+17"}
        for run, pot in values.items():
            touch(os.path.join(tmp, "mc", "MC_%d.root" % run))
            touch(os.path.join(tmp, "csv", "pot_%d.csv" % run))
            with open(os.path.join(tmp, "csv", "pot_%d.csv" % run), "w") as handle:
                handle.write("%d,%s\n" % (run, pot))
        touch(os.path.join(tmp, "mc", "MC_6.root"))                     # no csv at all
        bad = transfer.pot_outliers(tmp + "/mc", tmp + "/csv", "MC_*.root")
        self.assertEqual([r for r, _ in bad], [3, 4, 6])
        subprocess.run(["rm", "-rf", tmp])


class PotScriptTests(unittest.TestCase):
    def run_script(self, script, *args):
        return subprocess.run(["bash", script] + list(args), stdout=subprocess.PIPE, universal_newlines=True).stdout

    def test_mc_pattern_matches_original_script_and_genie_pattern(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "csv"))
        for r, pot in ((1, "1.1e+17"), (2, "1.2e+17"), (10, "1.0e+17")):
            touch(os.path.join(tmp, "mc", "MC_%d.root" % r))
            touch(os.path.join(tmp, "ghep", "gntp.%d.ghep.root" % r))
            with open(os.path.join(tmp, "csv", "pot_%d.csv" % r), "w") as handle:
                handle.write("%d,%s\n" % (r, pot))
        touch(os.path.join(tmp, "mc", "MC_11.root"))                     # no POT csv
        new = os.path.join(REPO, "helpers", "read_MC_POT.sh")
        original = os.path.join(os.path.dirname(REPO), "helper", "read_MC_POT.sh")
        out_new = self.run_script(new, tmp + "/mc", tmp + "/csv")
        if os.path.exists(original):
            self.assertEqual(out_new, self.run_script(original, tmp + "/mc", tmp + "/csv"))
        self.assertIn("Total POT          : 3.300000e+17", out_new)
        self.assertIn("Missing N          : 11", out_new)
        out_genie = self.run_script(new, tmp + "/ghep", tmp + "/csv", "gntp.*.ghep.root")
        self.assertIn("Files summed       : 3", out_genie)
        self.assertIn("Total POT          : 3.300000e+17", out_genie)
        subprocess.run(["rm", "-rf", tmp])


if __name__ == "__main__":
    unittest.main()
