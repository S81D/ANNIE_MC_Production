#!/bin/bash 
# Steven Doran

cat <<EOF
condor   dir: $CONDOR_DIR_INPUT 
process   id: $PROCESS 
output   dir: $CONDOR_DIR_OUTPUT 
EOF

HOSTNAME=$(hostname -f) 
GRIDUSER="doran"            

# Argument passed through job submission 
PART_NAME=$1

# Create a dummy log file in the output directory
DUMMY_OUTPUT_FILE=${CONDOR_DIR_OUTPUT}/${JOBSUBJOBID}_dummy_output 
touch ${DUMMY_OUTPUT_FILE} 

echo "This dummy file belongs to job ${PART_NAME}" >> ${DUMMY_OUTPUT_FILE}
start_time=$(date +%s)   # start time in seconds 
echo "The job started at: $(date)" >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}

# Copy datafiles from $CONDOR_INPUT onto worker node (/srv)
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/WCSim.tar.gz . 
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/gntp.${PART_NAME}.ghep.root . 
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/annie_tank_flux.${PART_NAME}.root . 

# un-tar TA
tar -xzf WCSim.tar.gz
rm WCSim.tar.gz

cd WCSim/build

echo "current directory:" >> ${DUMMY_OUTPUT_FILE}
pwd >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
echo "contents of directory:" >> ${DUMMY_OUTPUT_FILE}
ls -v >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}


# generate random seed
echo "random seed:" >> ${DUMMY_OUTPUT_FILE}
let "a=$RANDOM"
b="/WCSim/random/seed"
echo "$b $a" >> macros/setRandomParameters.mac
echo "$b $a" >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
echo "macros:" >> ${DUMMY_OUTPUT_FILE}
ls macros/ >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
echo "contents of setRandomParameters.mac" >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
cat macros/setRandomParameters.mac >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}

echo "Make sure singularity is bind mounting correctly (ls /cvmfs/singularity)" >> ${DUMMY_OUTPUT_FILE}
ls /cvmfs/singularity.opensciencegrid.org >> ${DUMMY_OUTPUT_FILE}

# Setup singularity container 
singularity exec -B/srv:/srv /cvmfs/singularity.opensciencegrid.org/anniesoft/wcsim\:latest/ $CONDOR_DIR_INPUT/wcsim_container.sh $PART_NAME


# cleanup and move files to $CONDOR_OUTPUT after leaving singularity environment
echo "Moving the output files to CONDOR OUTPUT..." >> ${DUMMY_OUTPUT_FILE} 
${JSB_TMP}/ifdh.sh cp -D /srv/logfile* $CONDOR_DIR_OUTPUT         # log files
${JSB_TMP}/ifdh.sh cp -D /srv/wcsim_${PART_NAME}.root $CONDOR_DIR_OUTPUT
#${JSB_TMP}/ifdh.sh cp -D /srv/wcsim_lappd_${PART_NAME}.root $CONDOR_DIR_OUTPUT

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
rm -rf /srv/WCSim
rm /srv/*.txt
rm /srv/*.root

echo "" >> ${DUMMY_OUTPUT_FILE}
echo "remaining contents:" >> ${DUMMY_OUTPUT_FILE}
ls -v /srv >> ${DUMMY_OUTPUT_FILE}

echo "" >> ${DUMMY_OUTPUT_FILE}
end_time=$(date +%s)
echo "Job ended at: $(date)" >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
duration=$((end_time - start_time))
echo "Script duration (s): ${duration}" >> ${DUMMY_OUTPUT_FILE}

### END ###
