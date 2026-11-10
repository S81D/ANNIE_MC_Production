#!/bin/bash
# WCSim worker (grid node): unpack WCSim, set the seed, run wcsim_container.sh in the wcsim image.
# Steven Doran; restructured for mcprod.
source "${CONDOR_DIR_INPUT}/job_common.sh"
mc_parse_args "$@"
mc_start "$@"

mc_stage_in wcsim_container.sh "gntp.${MC_run}.ghep.root" "annie_tank_flux.${MC_run}.root"
tar -xzf "${CONDOR_DIR_INPUT}/${MC_tarball}"
mv "gntp.${MC_run}.ghep.root" "annie_tank_flux.${MC_run}.root" WCSim/build/

cd WCSim/build
echo "/WCSim/random/seed ${MC_seed}" >> macros/setRandomParameters.mac     # the last seed line wins
for mac in WCSim.mac macros/primaries_directory.mac macros/setRandomParameters.mac macros/tuning_parameters.mac; do
    [ -f "${mac}" ] || continue
    mc_log "---- ${mac} (md5 $(md5sum < "${mac}" | cut -c1-32))"
    cat "${mac}" >> "${DUMMY}"
done
mc_container "${WORKDIR}/wcsim_container.sh"
cd "${WORKDIR}"

OUTPUTS="wcsim_${MC_run}.root"
[ "${MC_outputs}" = both ] && OUTPUTS="${OUTPUTS} wcsim_lappd_${MC_run}.root"
mc_outputs ${OUTPUTS}
mc_logs "wcsim_${MC_run}.log.gz"
mc_finish
