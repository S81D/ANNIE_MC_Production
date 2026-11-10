"""Fake-grid tests of the worker scripts: real job/container scripts, stubbed ifdh, singularity and payloads."""
import gzip
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STUBS = {
    "singularity": '#!/bin/bash\n# singularity exec -B <binds> <image> <cmd...>  ->  run <cmd...> here\n'
                   'shift; [ "$1" = -B ] && shift 2; shift; exec "$@"\n',
    "ifdh.sh": '#!/bin/bash\n# ifdh.sh cp -D <src...> <dest>\nshift; shift; dest="${@: -1}"; cp "${@:1:$#-1}" "$dest"\n',
    "gevgen_fnal": '#!/bin/bash\necho "gevgen_fnal $*"\n[ -n "$FAIL" ] && exit 1\n'
                   'while [ $# -gt 0 ]; do case $1 in -r) run=$2;; -m) maxpl=${2#+};; esac; shift; done\n'
                   'echo ghep > gntp.$run.ghep.root; echo maxpl > $maxpl\n'
                   'if [ -n "$GARBLE" ]; then echo "** Normalization for gen"; echo " ** PYTHIA banner **"; '
                   'echo "erated sample:      1.12088e+17 POT * detector"; '
                   'else echo "** Normalization for generated sample:      1.13339e+17${EXTRA} POT * detector"; fi\n',
    "root": '#!/bin/bash\necho "POTWEIGHT ${STUB_WEIGHT-1.13339e+17}"\n',     # unset: default; empty: unreadable
    "gntpc": '#!/bin/bash\nwhile [ $# -gt 0 ]; do case $1 in -i) in=$2;; -o) out=$2;; esac; shift; done\n'
             '[ -f "$in" ] && echo gst > "$out"\n',
}


def write_exec(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def make_tar(path, files):
    """files: {arcname: (text, executable)}"""
    src = tempfile.mkdtemp()
    for name, (text, executable) in files.items():
        full = os.path.join(src, name)
        (write_exec if executable else _write)(full, text)
    with tarfile.open(path, "w:gz") as tar:
        for top in {n.split("/")[0] for n in files}:
            tar.add(os.path.join(src, top), arcname=top)
    shutil.rmtree(src)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)


class Worker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mcprod_worker_")
        self.work, self.inp, self.out = (os.path.join(self.tmp, d) for d in ("srv", "input", "output"))
        for d in (self.work, self.inp, self.out):
            os.makedirs(d)
        for name, text in STUBS.items():
            write_exec(os.path.join(self.tmp, "bin" if name != "ifdh.sh" else "jsb", name), text)
        shutil.copy(os.path.join(REPO, "common/worker/job_common.sh"), self.inp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def give(self, *paths):
        for path in paths:
            shutil.copy(path if os.path.isabs(path) else os.path.join(REPO, path), self.inp)

    def give_file(self, name, text="data"):
        _write(os.path.join(self.inp, name), text)

    def run_job(self, stage, extra_env=None, **args):
        base = {"production": "t", "stage": stage, "run": 5, "test": 0, "seed": 6, "container": "/fake/image",
                "keep_logs": 1, "keep_failed_logs": 1, "commit": "abc", "config_sha": "def"}
        base.update(args)
        env = dict(os.environ, CONDOR_DIR_INPUT=self.inp, CONDOR_DIR_OUTPUT=self.out,
                   JSB_TMP=os.path.join(self.tmp, "jsb"), JOBSUBJOBID="99.0@jobsub01.fnal.gov",
                   PATH=os.path.join(self.tmp, "bin") + ":" + os.environ["PATH"],
                   MC_STAGEIN_WAIT="0", MC_MONITOR_INTERVAL="1")
        env.update(extra_env or {})
        argv = ["bash", os.path.join(REPO, stage, "worker", stage + "_job.sh")]
        argv += ["%s=%s" % kv for kv in base.items()]
        proc = subprocess.run(argv, cwd=self.work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True, timeout=120)
        return proc

    def outputs(self):
        return sorted(os.listdir(self.out))

    def manifest(self):
        name = [f for f in self.outputs() if f.endswith("_manifest.json")][0]
        with open(os.path.join(self.out, name)) as handle:
            return json.load(handle)

    def dummy(self):
        name = [f for f in self.outputs() if f.endswith("_dummy_output")][0]
        with open(os.path.join(self.out, name)) as handle:
            return handle.read()


class GenieWorker(Worker):
    def prepare(self):
        self.give("genie/worker/genie_container.sh", "genie/worker/run_annie_genie.sh", "common/geometry/annie_v07.gdml")
        self.give_file("gsimple_flux_5.root")
        _write(os.path.join(self.tmp, "cvmfs", "gxspl-FNALsmall.xml"), "spline")
        _write(os.path.join(self.tmp, "setup_genie.sh"), "export GENIE=/fake\n")
        return dict(events=20000, software="builtin", tune="G18_10a_02_11a", tank_topvol="TWATER_LV",
                    geometry="annie_v07.gdml", flux_file="gsimple_flux_5.root",
                    spline=os.path.join(self.tmp, "cvmfs", "gxspl-FNALsmall.xml"))

    def ghep_log(self):
        with gzip.open(os.path.join(self.out, "gntp.5.ghep.log.gz"), "rt") as handle:
            return handle.read()

    def test_world_success(self):
        args = self.prepare()
        proc = self.run_job("genie", {"GENIE_SETUP": os.path.join(self.tmp, "setup_genie.sh")}, volume="world", **args)
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:])
        for name in ("gntp.5.ghep.root", "gntp.5.gst.root", "pot_5.csv", "gntp.5.ghep.log.gz", "BNBFlux5.xml",
                     "ANNIE-5.maxpl.xml"):
            self.assertIn(name, self.outputs())
        with open(os.path.join(self.out, "pot_5.csv")) as handle:
            self.assertEqual(handle.read().strip(), "5,1.13339e+17")
        self.assertIn("from gtree weight (gtree weight: 1.13339e+17, log: 1.13339e+17)\n", self.dummy())
        log = self.ghep_log()
        for expected in ("-t WORLD_LV", "-z -10", "--seed 6", "gsimple_flux_5.root,ANNIE-rock",
                         "--cross-sections gxspl-FNALsmall.xml", "-g annie_v07.gdml", "--tune G18_10a_02_11a",
                         "-n 20000"):
            self.assertIn(expected, log)
        with open(os.path.join(self.out, "BNBFlux5.xml")) as handle:
            self.assertIn("<upstreamz> -10.0 </upstreamz>", handle.read())
        m = self.manifest()
        self.assertEqual((m["status"], m["seed"], m["run"]), ("ok", 6, 5))
        self.assertTrue(self.dummy().rstrip().endswith("DONE"))

    def pot_case(self, env):
        args = self.prepare()
        env = dict(env, GENIE_SETUP=os.path.join(self.tmp, "setup_genie.sh"))
        proc = self.run_job("genie", env, volume="world", **args)
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:])
        with open(os.path.join(self.out, "pot_5.csv")) as handle:
            return handle.read().strip()

    def test_pot_from_gtree_when_log_garbled(self):
        self.assertEqual(self.pot_case({"GARBLE": "1", "STUB_WEIGHT": "1.12088e+17"}), "5,1.12088e+17")
        self.assertIn("[log and gtree weight differ]", self.dummy())

    def test_pot_from_gtree_when_log_has_extra_digit(self):
        self.assertEqual(self.pot_case({"EXTRA": "1"}), "5,1.13339e+17")       # log says 1.13339e+171
        self.assertIn("log: 1.13339e+171) [log and gtree weight differ]", self.dummy())

    def test_pot_from_log_when_weight_unreadable(self):
        self.assertEqual(self.pot_case({"STUB_WEIGHT": ""}), "5,1.13339e+17")
        self.assertIn("from log (gtree weight unreadable)", self.dummy())

    def test_tank_mode(self):
        args = self.prepare()
        proc = self.run_job("genie", {"GENIE_SETUP": os.path.join(self.tmp, "setup_genie.sh")}, volume="tank", **args)
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:])
        log = self.ghep_log()
        self.assertIn("-t TWATER_LV", log)
        self.assertIn("gsimple_flux_5.root,ANNIE-tank", log)
        self.assertNotIn("-z -10", log)

    def test_failure_exit_4_and_logs(self):
        args = self.prepare()
        proc = self.run_job("genie", {"GENIE_SETUP": os.path.join(self.tmp, "setup_genie.sh"), "FAIL": "1"},
                            volume="world", **args)
        self.assertEqual(proc.returncode, 4)
        self.assertNotIn("gntp.5.ghep.root", self.outputs())
        self.assertIn("gntp.5.ghep.log.gz", self.outputs())
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertIn("MCPROD_STATUS=failed exit=4", self.dummy())


class AnniedirtWorker(Worker):
    def test_seeded_run(self):
        image = os.path.join(self.tmp, "img")
        _write(os.path.join(image, "Geant4_install/bin/geant4.sh"), "")
        _write(os.path.join(image, "setup_Dockerfile.sh"), "")
        write_exec(os.path.join(image, "ANNIEDirt_install/bin/g4annie_dirt_flux"),
                   '#!/bin/bash\necho "args: $*"\nwhile [ $# -gt 0 ]; do case $1 in -o) out=$2; shift;; *.mac) '
                   'echo "/control/execute $1"; cat $1;; esac; shift; done\necho flux > $out\n')
        self.give("anniedirt/worker/anniedirt_container.sh", "common/geometry/annie_v07.gdml",
                  "common/geometry/gdml_schema.tar.gz")
        self.give_file("gntp.5.ghep.root")
        proc = self.run_job("anniedirt", {"IMAGE_ROOT": image}, events=20000, geometry="annie_v07.gdml")
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:])
        self.assertIn("annie_tank_flux.5.root", self.outputs())
        with gzip.open(os.path.join(self.out, "annie_tank_flux.5.log.gz"), "rt") as handle:
            log = handle.read()
        self.assertIn("/random/setSeeds 6 1000009", log)
        self.assertIn("--physics=FTFP_BERT_HP", log)
        self.assertIn("-i ./gntp.5.ghep.root", log)
        self.assertTrue(os.path.exists(os.path.join(self.work, "gdml.xsd")))


class WCSimWorker(Worker):
    def prepare(self):
        wcsim = ('#!/bin/bash\necho "seed line: $(tail -1 macros/setRandomParameters.mac)"\n'
                 '[ -n "$FAIL" ] && exit 1\nls gntp.5.ghep.root annie_tank_flux.5.root\n'
                 'echo pmt > wcsim_0.root; echo lappd > wcsim_lappd_0.root\n')
        make_tar(os.path.join(self.inp, "WCSim.tar.gz"), {
            "WCSim/build/WCSim": (wcsim, True), "WCSim/build/sourceme": ("", False),
            "WCSim/build/WCSim.mac": ("/run/beamOn 20000\n", False),
            "WCSim/build/macros/setRandomParameters.mac": ("/WCSim/random/seed 31415\n", False)})
        self.give("wcsim/worker/wcsim_container.sh")
        self.give_file("gntp.5.ghep.root")
        self.give_file("annie_tank_flux.5.root")

    def test_both_outputs_no_logs(self):
        self.prepare()
        proc = self.run_job("wcsim", tarball="WCSim.tar.gz", outputs="both", keep_logs=0, keep_failed_logs=0)
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:])
        self.assertIn("wcsim_5.root", self.outputs())
        self.assertIn("wcsim_lappd_5.root", self.outputs())
        self.assertNotIn("wcsim_5.log.gz", self.outputs())
        self.assertIn("/WCSim/random/seed 6", self.dummy())
        self.assertIn("/run/beamOn 20000", self.dummy())

    def test_pmt_only(self):
        self.prepare()
        self.run_job("wcsim", tarball="WCSim.tar.gz", outputs="pmt", keep_logs=0, keep_failed_logs=0)
        self.assertNotIn("wcsim_lappd_5.root", self.outputs())

    def test_failed_logs_only_when_asked(self):
        self.prepare()
        proc = self.run_job("wcsim", {"FAIL": "1"}, tarball="WCSim.tar.gz", outputs="both", keep_logs=0,
                            keep_failed_logs=0)
        self.assertEqual(proc.returncode, 4)
        self.assertNotIn("wcsim_5.log.gz", self.outputs())


class ToolchainWorker(Worker):
    def prepare(self, fail=False):
        analyse = '#!/bin/bash\necho "Analyse $*"\n' + ('' if fail else 'echo tree > tree.root\n')
        make_tar(os.path.join(self.inp, "TA.tar.gz"), {
            "TA/Analyse": (analyse, True), "TA/Setup.sh": ("", False),
            "TA/configfiles/PMTWaveformSim/ToolChainConfig": ("", False)})
        self.give("toolchain/worker/toolchain_container.sh", "toolchain/hooks/config_GENIE.py")
        self.give_file("wcsim_5.root")
        self.give_file("gntp.5.ghep.root")
        return dict(tarball="TA.tar.gz", ta_folder="TA", toolchain="PMTWaveformSim", output_file="tree.root",
                    attach_lappd=0, hook="config_GENIE.py", keep_logs=0, keep_failed_logs=1)

    def test_success_and_hook(self):
        proc = self.run_job("toolchain", **self.prepare())
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:])
        self.assertIn("MC_5.root", self.outputs())
        self.assertNotIn("toolchain_5.log.gz", self.outputs())
        self.assertIn("InputFile wcsim_5.root", self.dummy())
        self.assertTrue(os.path.exists(os.path.join(self.work, "TA", "wcsim_5.root")))

    def test_failure_returns_log_when_asked(self):
        proc = self.run_job("toolchain", **self.prepare(fail=True))
        self.assertEqual(proc.returncode, 4)
        self.assertIn("toolchain_5.log.gz", self.outputs())


if __name__ == "__main__":
    unittest.main()
