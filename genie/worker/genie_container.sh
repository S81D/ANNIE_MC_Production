#!/usr/bin/env bash
# Runs inside the genie3 image: set up GENIE, generate one run, make the gst tree, record the POT.
GENIE_SETUP=${GENIE_SETUP:-/Genie/GENIE-v3-master/annie/Setup_GENIE.sh}     # the image's own GENIE
if [ "${MC_software}" = tarball ]; then
    source ./Setup_GENIE.sh "${MC_tarball_folder}"
else
    source "${GENIE_SETUP}"
fi
echo "gevgen_fnal: $(which gevgen_fnal)" >> "${DUMMY}"

if [ "${MC_volume}" = tank ]; then
    VOLUME="--tank --topvol ${MC_tank_topvol}"          # UNTESTED
else
    VOLUME="--topvol WORLD_LV"                           # rock generation (run_annie_genie.sh default)
fi
chmod +x run_annie_genie.sh
./run_annie_genie.sh -o . -r "${MC_run}" -n "${MC_events}" -f "${MC_flux_file}" -x "$(basename "${MC_spline}")" \
    -g "${MC_geometry}" --seed "${MC_seed}" ${VOLUME} --tune "${MC_tune}"

gntpc -i "gntp.${MC_run}.ghep.root" -f gst -o "gntp.${MC_run}.gst.root"
POT=$(grep "Normalization for generated sample" "gntp.${MC_run}.ghep.log" | awk '{print $6}')
echo "${MC_run},${POT}" > "pot_${MC_run}.csv"
echo "POT for run ${MC_run}: ${POT}" >> "${DUMMY}"
gzip -9 "gntp.${MC_run}.ghep.log"
