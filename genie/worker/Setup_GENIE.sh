#! /usr/bin/env bash

# this file will only be sourced IF a local copy of GENIE is being used

Gfolder=/srv/$1    # /src/GENIE_FOLDER_NAME

export GENIE=${Gfolder}
export LIBGL_ALWAYS_INDIRECT=1
export DISPLAY=:0
export ROOTSYS=/Genie/root-6.24.06/install/
export LD_LIBRARY_PATH=/lib:.:/Genie/log4cpp/install/lib:/Genie/Pythia6Support/v6_424/lib:${ROOTSYS}/lib:/Genie/LHAPDF-6.3.0/install/lib:${GENIE}/install/lib:${LD_LIBRARY_PATH}
export PYTHIA6_DIR=/Genie/Pythia6Support/v6_424/
export PYTHIA6_INCLUDE_DIR=/Genie/Pythia6Support/v6_424/inc/
export PYTHIA6_LIBRARY=/Genie/Pythia6Support/v6_424/lib/
export LHAPATH=/Genie/LHAPDF-6.3.0/install/share/LHAPDF:${LHAPATH}
export PATH=.:/Genie/fsplit/:${ROOTSYS}/bin:/Genie/LHAPDF-6.3.0/install/bin:${GENIE}/install/bin:${PATH}
export MANPATH=${ROOTSYS}/bin:${MANPATH}
export PYTHONPATH=${ROOTSYS}/lib:${PYTHONPATH}