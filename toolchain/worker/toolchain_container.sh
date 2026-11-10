#!/bin/bash
# Runs inside the toolanalysis image: run the configured toolchain over one WCSim + GENIE file.
# Steven Doran; restructured for mcprod.
LOG="${WORKDIR}/toolchain_${MC_run}.log"
cd "${MC_ta_folder}"

if [ -n "${MC_hook}" ]; then         # per-run config writer (default toolchain/hooks/config_GENIE.py)
    cp "${WORKDIR}/${MC_hook}" "configfiles/${MC_toolchain}/"
    ( cd "configfiles/${MC_toolchain}" && python3 "${MC_hook}" "${MC_run}" )
    for cfg in LoadWCSimConfig PhaseIITreeMakerConfig; do
        [ -f "configfiles/${MC_toolchain}/${cfg}" ] || continue
        echo "---- ${cfg}" >> "${DUMMY}"
        cat "configfiles/${MC_toolchain}/${cfg}" >> "${DUMMY}"
    done
fi

source Setup.sh
./Analyse "configfiles/${MC_toolchain}/ToolChainConfig" > "${LOG}" 2>&1

mv "${MC_output_file}" "${WORKDIR}/MC_${MC_run}.root"
gzip -9 "${LOG}"
