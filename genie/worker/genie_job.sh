#!/bin/bash
# GENIE worker (grid node): stage inputs, run genie_container.sh in the genie3 image, return outputs.
# Steven Doran (based on James Minock's scripts); restructured for mcprod.
source "${CONDOR_DIR_INPUT}/job_common.sh"
mc_parse_args "$@"
mc_start "$@"

mc_stage_in genie_container.sh run_annie_genie.sh "${MC_geometry}" "${MC_flux_file}"
cp "${MC_spline}" . || mc_log "could not read the spline from CVMFS: ${MC_spline}"
if [ "${MC_software}" = tarball ]; then
    mc_stage_in Setup_GENIE.sh
    tar -xzf "${CONDOR_DIR_INPUT}/${MC_tarball}"
    ls -lh "${MC_tarball_folder}" >> "${DUMMY}"
fi

mc_container ./genie_container.sh

mc_outputs "gntp.${MC_run}.ghep.root" "gntp.${MC_run}.gst.root" "pot_${MC_run}.csv"
mc_logs "gntp.${MC_run}.ghep.log.gz" "BNBFlux${MC_run}.xml" "ANNIE-${MC_run}.maxpl.xml"
mc_finish
