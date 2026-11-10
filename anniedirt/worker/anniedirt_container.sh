#!/usr/bin/env bash
# Runs inside the g4dirt image: propagate one run's GENIE final-state particles to the tank.
# Same command as the image's /home/run_g4dirt.sh, plus a seed macro: run_g4dirt.sh never seeds Geant4.
# g4annie_dirt_flux executes extra arguments as macros before the event loop, also in --batch mode.
IMAGE_ROOT=${IMAGE_ROOT:-}          # tests point this at stubs
source "${IMAGE_ROOT}/Geant4_install/bin/geant4.sh"
source "${IMAGE_ROOT}/setup_Dockerfile.sh"

printf '/random/setSeeds %d %d\n' "${MC_seed}" "$(( MC_seed + 1000003 ))" > seed.mac
LOG="annie_tank_flux.${MC_run}.log"
CMD="${IMAGE_ROOT}/ANNIEDirt_install/bin/g4annie_dirt_flux --batch -n ${MC_events} -g ${MC_geometry} --physics=FTFP_BERT_HP \
-i ./gntp.${MC_run}.ghep.root -o annie_tank_flux.${MC_run}.root seed.mac"
{ echo "command: ${CMD}"; echo "seed.mac: $(cat seed.mac)"; echo; } > "${LOG}"
${CMD} >> "${LOG}" 2>&1

rm -f currentEvent.rndm currentRun.rndm
gzip -9 "${LOG}"
