"""Build the software tarballs shipped with the jobs (WCSim, ToolAnalysis, custom GENIE)."""
import hashlib
import json
import os
import subprocess
import tarfile

from . import REPO, records
from .config import ConfigError


class _Hashing:
    """File wrapper that md5s everything written through it."""
    def __init__(self, handle):
        self.handle, self.md5, self.size = handle, hashlib.md5(), 0

    def write(self, data):
        self.md5.update(data)
        self.size += len(data)
        return self.handle.write(data)

    def flush(self):
        self.handle.flush()

    def close(self):
        self.handle.close()


def _git_info(path):
    def git(*args):
        proc = subprocess.run(["git", "-C", path] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              universal_newlines=True)
        return proc.stdout.strip() if proc.returncode == 0 else None
    commit = git("rev-parse", "HEAD")
    if not commit:
        return {"git": None}
    status = git("status", "--porcelain", "--untracked-files=no") or ""
    diff = git("diff", "HEAD") or ""
    return {"git": {"commit": commit, "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                    "remote": git("config", "--get", "remote.origin.url"), "dirty": bool(status),
                    "diff_md5": hashlib.md5(diff.encode()).hexdigest() if diff else None}}


def source_of(cfg, stage):
    """(parent dir, folder name inside the tarball, output path)."""
    c = cfg[stage]
    folder = {"wcsim": "WCSim", "toolchain": c.get("ta_folder"), "genie": c.get("tarball_folder")}[stage]
    if not c.get("source_dir") or not folder or not c.get("tarball"):
        raise ConfigError("%s: set %s.source_dir, %s.tarball and the folder name (%s)" % (
            stage, stage, stage, {"wcsim": "always WCSim", "toolchain": "toolchain.ta_folder",
                                  "genie": "genie.tarball_folder"}[stage]))
    return c["source_dir"], folder, c["tarball"]


def build(cfg, stage):
    parent, folder, out = source_of(cfg, stage)
    src = os.path.join(parent, folder)
    if not os.path.isdir(src):
        raise SystemExit("source folder %s does not exist" % src)
    if os.path.exists(out):
        raise SystemExit("%s already exists. dCache cannot overwrite: remove it yourself or give the new tarball "
                         "another name in %s.tarball" % (out, stage))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    skip_git = lambda info: None if ".git" in info.name.split("/") else info    # autoANNIE: 1.7 -> 0.6 GB
    records.say("Writing %s from %s (excluding .git) ..." % (out, src))
    sink = _Hashing(open(out, "wb"))
    with tarfile.open(fileobj=sink, mode="w:gz") as tar:
        tar.add(src, arcname=folder, filter=skip_git)
        if stage == "wcsim" and not os.path.exists(os.path.join(src, "build", "sourceme")):
            tar.add(os.path.join(REPO, "wcsim", "sourceme"), arcname="WCSim/build/sourceme")
            records.say("  added wcsim/sourceme as WCSim/build/sourceme")
    sink.close()
    info = {"tarball": out, "md5": sink.md5.hexdigest(), "bytes": sink.size, "built": records.now(),
            "source": src, "folder": folder, "builder": cfg["production"]["user"]}
    info.update(_git_info(src))
    with open(out + ".provenance.json", "w") as handle:
        json.dump(info, handle, indent=1)
    return info
