#!/bin/bash
# Author: Steven Doran

# job name is: MC_toolchain_N  (N passed through submission)

cat <<EOF
condor   dir: $CONDOR_DIR_INPUT
process   id: $PROCESS
output   dir: $CONDOR_DIR_OUTPUT
EOF

HOSTNAME=$(hostname -f)

# ****************************************************** #
GRIDUSER="doran"               # adjust accordingly!
TA_folder=NC_CC_Nov_6_2025     # adjust accordingly!
# ****************************************************** #

# part name
FIRST_ARG=$1
RUN=$(echo "$FIRST_ARG" | grep -oE '[0-9]+')

# Create a dummy log file in the output directory
DUMMY_OUTPUT_FILE=${CONDOR_DIR_OUTPUT}/${FIRST_ARG}_${JOBSUBJOBID}_dummy_output
touch ${DUMMY_OUTPUT_FILE}
echo "This dummy file belongs to job ${FIRST_ARG}" >> ${DUMMY_OUTPUT_FILE} 
start_time=$(date +%s)   # start time in seconds 
echo "The job started at: $(date)" >> ${DUMMY_OUTPUT_FILE} 
echo "" >> ${DUMMY_OUTPUT_FILE} 

echo "Files present in CONDOR_INPUT:" >> ${DUMMY_OUTPUT_FILE} 
ls -lrth $CONDOR_DIR_INPUT >> ${DUMMY_OUTPUT_FILE} 
echo "" >> ${DUMMY_OUTPUT_FILE} 

# Copy datafiles from $CONDOR_INPUT onto worker node (/srv)
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/wcsim* .
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/MyToolAnalysis_grid.tar.gz .

echo "Sleeping for 30s to wait for files to land..." >> ${DUMMY_OUTPUT_FILE} 
sleep 30

# un-tar TA
tar -xzf MyToolAnalysis_grid.tar.gz
rm MyToolAnalysis_grid.tar.gz

FILES_PRESENT=$(ls /srv/wcsim* 2>/dev/null | wc -l)
echo "*** There are $FILES_PRESENT files here ***" >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
echo "wcsim files present:" >> ${DUMMY_OUTPUT_FILE}
ls -v /srv/wcsim* >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}

echo "Make sure singularity is bind mounting correctly (ls /cvmfs/singularity)" >> ${DUMMY_OUTPUT_FILE}
ls /cvmfs/singularity.opensciencegrid.org >> ${DUMMY_OUTPUT_FILE}

# Setup singularity container
singularity exec -B/srv:/srv /cvmfs/singularity.opensciencegrid.org/anniesoft/toolanalysis:latest/ $CONDOR_DIR_INPUT/run_container_job.sh $RUN

# ------ The script run_container_job.sh will now run within singularity ------ #

# cleanup and move files to $CONDOR_OUTPUT after leaving singularity environment
echo "Moving the output files to CONDOR OUTPUT..." >> ${DUMMY_OUTPUT_FILE}
${JSB_TMP}/ifdh.sh cp -D /srv/logfile*.txt $CONDOR_DIR_OUTPUT     # log files
${JSB_TMP}/ifdh.sh cp -D /srv/MC_${RUN}.root $CONDOR_DIR_OUTPUT   # Modify: any .root files etc.. that are produced from your toolchain

echo "" >> ${DUMMY_OUTPUT_FILE}
echo "Input:" >> ${DUMMY_OUTPUT_FILE}
ls $CONDOR_DIR_INPUT >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
echo "Output:" >> ${DUMMY_OUTPUT_FILE}
ls $CONDOR_DIR_OUTPUT >> ${DUMMY_OUTPUT_FILE}

echo "" >> ${DUMMY_OUTPUT_FILE}
echo "Cleaning up..." >> ${DUMMY_OUTPUT_FILE}
echo "srv directory:" >> ${DUMMY_OUTPUT_FILE}
ls -v /srv >> ${DUMMY_OUTPUT_FILE}

# make sure to clean up the files left on the worker node
rm /srv/*.root
rm /srv/*.txt
rm /srv/*.sh
rm -rf /srv/${TA_folder}/

echo "" >> ${DUMMY_OUTPUT_FILE}
echo "Leftovers:" >> ${DUMMY_OUTPUT_FILE}
ls -v /srv >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}

end_time=$(date +%s) 
echo "Job ended at: $(date)" >> ${DUMMY_OUTPUT_FILE} 
echo "" >> ${DUMMY_OUTPUT_FILE} 
duration=$((end_time - start_time)) 
echo "Script duration (s): ${duration}" >> ${DUMMY_OUTPUT_FILE} 

### END ###
