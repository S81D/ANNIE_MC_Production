#!/bin/bash
# MC toolchain worker (grid node): unpack ToolAnalysis, add one WCSim + GENIE file, run toolchain_container.sh.
# Steven Doran; restructured for mcprod.
source "${CONDOR_DIR_INPUT}/job_common.sh"
mc_parse_args "$@"
mc_start "$@"

INPUTS="wcsim_${MC_run}.root gntp.${MC_run}.ghep.root"
[ "${MC_attach_lappd}" = 1 ] && INPUTS="${INPUTS} wcsim_lappd_${MC_run}.root"
HOOK=""
[ "${MC_hook}" != tarball ] && HOOK=${MC_hook}          # repo config script, shipped with the job
mc_stage_in toolchain_container.sh ${INPUTS} ${HOOK}
tar -xzf "${CONDOR_DIR_INPUT}/${MC_tarball}"
mv ${INPUTS} "${MC_ta_folder}/"

# Record which config script writes the per-run configs, and how it compares with the tarball's own copy
OWN="${MC_ta_folder}/configfiles/${MC_toolchain}/config_GENIE.py"
md5_of() { if [ -f "$1" ]; then md5sum < "$1" | cut -c1-32; else echo absent; fi; }
if [ -z "${HOOK}" ]; then
    mc_log "config script: the tarball's configfiles/${MC_toolchain}/config_GENIE.py (md5 $(md5_of "${OWN}"))"
else
    if [ ! -f "${OWN}" ]; then SAME="absent"
    elif cmp -s "${HOOK}" "${OWN}"; then SAME="identical"
    else SAME="different, md5 $(md5_of "${OWN}"), not used"; fi
    mc_log "config script: ${HOOK} from the repo (md5 $(md5_of "${HOOK}")); tarball's config_GENIE.py: ${SAME}"
fi

mc_container ./toolchain_container.sh

mc_outputs "MC_${MC_run}.root"
mc_logs "toolchain_${MC_run}.log.gz"
mc_finish
