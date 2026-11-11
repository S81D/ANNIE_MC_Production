#!/bin/bash
# Runs inside the toolanalysis image: run the configured toolchain over one WCSim + GENIE file.
# Steven Doran; restructured for mcprod.
LOG="${WORKDIR}/toolchain_${MC_run}.log"
cd "${MC_ta_folder}"

# Per-run config script (toolchain/README.md): writes LoadWCSimConfig (InputFile wcsim_N.root) and the tree maker config
if [ "${MC_hook}" = tarball ]; then
    HOOK=config_GENIE.py
else
    HOOK=${MC_hook}
    cp "${WORKDIR}/${MC_hook}" "configfiles/${MC_toolchain}/"
fi
if ! ( cd "configfiles/${MC_toolchain}" && python3 "${HOOK}" "${MC_run}" ) >> "${LOG}" 2>&1; then
    # never run Analyse on stale configs: it would process whichever file the old InputFile names
    echo "config script FAILED: configfiles/${MC_toolchain}/${HOOK} missing or raised an error (see the log)" >> "${DUMMY}"
    gzip -9 "${LOG}"
    exit 3
fi
for cfg in LoadWCSimConfig PhaseIITreeMakerConfig; do
    [ -f "configfiles/${MC_toolchain}/${cfg}" ] || continue
    echo "---- ${cfg}" >> "${DUMMY}"
    cat "configfiles/${MC_toolchain}/${cfg}" >> "${DUMMY}"
done

source Setup.sh
./Analyse "configfiles/${MC_toolchain}/ToolChainConfig" >> "${LOG}" 2>&1

mv "${MC_output_file}" "${WORKDIR}/MC_${MC_run}.root"
gzip -9 "${LOG}"
