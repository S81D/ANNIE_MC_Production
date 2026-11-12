RUN=$1
BATCH=$2

QE_tag="QE_1.50"

export INPUT_PATH=/pnfs/annie/scratch/users/doran/grid_wcsim_sample/                  

echo ""
echo "submitting job..."
echo ""

OUTPUT_FOLDER=/pnfs/annie/scratch/users/doran/output/wcsim/AmBe/pmt_tilting_v1/${QE_tag}/${BATCH}/
mkdir -p $OUTPUT_FOLDER                                                 

# default grid resources:
# - 2 GB memory
# - 6 hr lifetime
# - 10 GB disk

# wrapper script to submit your grid job
jobsub_submit --memory=2000MB --expected-lifetime=2h -G annie --disk=2GB --resource-provides=usage_model=OFFSITE --blacklist=Omaha,Swan,Wisconsin,SU-ITS,RAL -f ${INPUT_PATH}/hold/${BATCH}/WCSim.tar.gz -f ${INPUT_PATH}/wcsim_container.sh -d OUTPUT $OUTPUT_FOLDER file://${INPUT_PATH}/run_job.sh ${RUN} ${BATCH}

