#!/bin/bash
# anniedirt worker (grid node): stage the GENIE file + geometry, run anniedirt_container.sh in the g4dirt image.
# Steven Doran; restructured for mcprod.
source "${CONDOR_DIR_INPUT}/job_common.sh"
mc_parse_args "$@"
mc_start "$@"

mc_stage_in anniedirt_container.sh "${MC_geometry}" gdml_schema.tar.gz "gntp.${MC_run}.ghep.root"
tar -xzf gdml_schema.tar.gz && rm gdml_schema.tar.gz      # GDML .xsd schemas Geant4 needs to parse the geometry

mc_container ./anniedirt_container.sh

mc_outputs "annie_tank_flux.${MC_run}.root"
mc_logs "annie_tank_flux.${MC_run}.log.gz"
mc_finish
