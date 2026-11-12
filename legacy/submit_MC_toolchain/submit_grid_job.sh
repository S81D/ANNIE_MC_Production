#!/bin/bash
# Author: Steven Doran

RUN=$1

export INPUT_PATH=/pnfs/annie/scratch/users/doran/grid_wcsim/submit_MC_toolchain/
export OUTPUT_FOLDER=/pnfs/annie/scratch/users/doran/output/genie_muons/Trees/thru/individual_tilt/
export WCSIM_FILES_PATH=/pnfs/annie/scratch/users/doran/output/genie_muons/thru_individual_tilts/

mkdir -p $OUTPUT_FOLDER

# Create a list of part files to attach
IFS=':' read -ra FILES <<< "$PROCESSED_FILES_PATH"
PART_FILES=""
for FILE in "${FILES[@]}"; do
    if [[ -f "$FILE" ]]; then
        PART_FILES="$PART_FILES -f $FILE"
    fi
done


# for testing / verbose
#echo "Attaching the following files:"
#for FILE in "${FILES[@]}"; do
#    if [[ -f "$FILE" ]]; then
#        echo "$FILE"
#    else
#        echo "[WARNING] File not found: $FILE"
#    fi
#done


jobsub_submit --memory=2000MB --expected-lifetime=3h -G annie --disk=5GB --resource-provides=usage_model=OFFSITE --blacklist=Omaha,Swan,Wisconsin,RAL $PART_FILES -f ${INPUT_PATH}/run_container_job.sh -f ${INPUT_PATH}/MyToolAnalysis_grid.tar.gz -d OUTPUT $OUTPUT_FOLDER file://${INPUT_PATH}/grid_job.sh MC_toolchain_${RUN} 

echo "job name is: MC_toolchain_${RUN}"
echo "" 
