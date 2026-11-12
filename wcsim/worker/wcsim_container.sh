#!/bin/bash
# Runs inside the wcsim image, in WCSim/build: simulate one run's GENIE + dirt events.
# Steven Doran; restructured for mcprod.
LOG="${WORKDIR}/wcsim_${MC_run}.log"
source sourceme >> "${LOG}" 2>&1
chmod +x WCSim
./WCSim WCSim.mac >> "${LOG}" 2>&1

mv wcsim_0.root "${WORKDIR}/wcsim_${MC_run}.root"
if [ "${MC_outputs}" = both ]; then
    mv wcsim_lappd_0.root "${WORKDIR}/wcsim_lappd_${MC_run}.root"
else
    rm -f wcsim_*lappd*.root
fi
gzip -9 "${LOG}"
