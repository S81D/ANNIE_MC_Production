#!/usr/bin/env python3
"""Print 'run,POT' for gntp.N.ghep.root files, from the gtree weight (GENIE's own POT record). Read-only.

Use it to check or rebuild pot_N.csv files whose log-scraped value was lost or garbled. Run it in the
toolanalysis image (python3.8 + PyROOT):

  singularity exec -B /pnfs:/pnfs /cvmfs/singularity.opensciencegrid.org/anniesoft/toolanalysis:latest/ \\
    bash -c 'unset PYTHONPATH; source /usr/local/bin/thisroot.sh; python3.8 helpers/pot_from_ghep.py <ghep_dir> [runs]'

runs: comma-separated (default: every gntp.N.ghep.root in the directory). Output format = pot_N.csv.
"""
import glob
import os
import re
import sys

import ROOT

ROOT.gErrorIgnoreLevel = ROOT.kError


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    directory = sys.argv[1]
    if len(sys.argv) > 2:
        runs = [int(r) for r in sys.argv[2].split(",") if r]
    else:
        names = (os.path.basename(p) for p in glob.glob(os.path.join(directory, "gntp.*.ghep.root")))
        runs = sorted(int(m.group(1)) for m in (re.match(r"gntp\.(\d+)\.ghep\.root$", n) for n in names) if m)
    for run in runs:
        try:
            handle = ROOT.TFile.Open(os.path.join(directory, "gntp.%d.ghep.root" % run))
        except OSError:                      # newer ROOT raises; 6.24 returns a null file
            handle = None
        tree = handle.Get("gtree") if handle and not handle.IsZombie() else None
        if tree:
            print("%d,%.6g" % (run, tree.GetWeight()))
        else:
            print("%d,UNREADABLE" % run, file=sys.stderr)


if __name__ == "__main__":
    main()
