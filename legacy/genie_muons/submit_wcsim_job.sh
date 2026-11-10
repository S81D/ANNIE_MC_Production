RUN=$1
BATCH=$2

export INPUT_PATH=/pnfs/annie/scratch/{USER}/doran/grid_wcsim/                  

echo ""
echo "submitting job..."
echo ""

QUEUE=medium 

OUTPUT_FOLDER=/pnfs/annie/scratch/users/{USER}/output/genie_muons/${BATCH}
mkdir -p $OUTPUT_FOLDER                                                 

# wrapper script to submit your grid job
jobsub_submit --memory=2000MB --expected-lifetime=6h -G annie --disk=5GB --resource-provides=usage_model=OFFSITE --blacklist=Omaha,Swan,Wisconsin,SU-ITS,RAL -f ${INPUT_PATH}/WCSim.tar.gz -f ${INPUT_PATH}/wcsim_container.sh -f ${INPUT_PATH}/submit/${RUN}/WCSim.mac -d OUTPUT $OUTPUT_FOLDER file://${INPUT_PATH}/run_job.sh ${RUN} ${BATCH}

