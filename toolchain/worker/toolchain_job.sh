#!/bin/bash
# MC toolchain worker (grid node): unpack ToolAnalysis, add one WCSim + GENIE file, run toolchain_container.sh.
# Steven Doran; restructured for mcprod.
source "${CONDOR_DIR_INPUT}/job_common.sh"
mc_parse_args "$@"
mc_start "$@"

INPUTS="wcsim_${MC_run}.root gntp.${MC_run}.ghep.root"
[ "${MC_attach_lappd}" = 1 ] && INPUTS="${INPUTS} wcsim_lappd_${MC_run}.root"
mc_stage_in toolchain_container.sh ${INPUTS} ${MC_hook}
tar -xzf "${CONDOR_DIR_INPUT}/${MC_tarball}"
mv ${INPUTS} "${MC_ta_folder}/"

mc_container ./toolchain_container.sh

mc_outputs "MC_${MC_run}.root"
mc_logs "toolchain_${MC_run}.log.gz"
mc_finish
