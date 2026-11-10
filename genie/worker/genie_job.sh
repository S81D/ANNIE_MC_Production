#!/bin/bash

cat <<EOF
condor   dir: $CONDOR_DIR_INPUT
process   id: $PROCESS
output   dir: $CONDOR_DIR_OUTPUT
EOF

HOSTNAME=$(hostname -f)

# run number and user name passed through arguments
RUN=$1
GRIDUSER=$2
GEOFILE=$3
USE_LOCAL_GENIE=$4
if [ "$USE_LOCAL_GENIE" = true ]; then
    GENIE_TAR_NAME=$5
    GENIE_FOLDER_NAME=$6
fi

# Create a dummy log file in the output directory
DUMMY_OUTPUT_FILE=${CONDOR_DIR_OUTPUT}/${RUN}_${JOBSUBJOBID}_dummy_output
touch ${DUMMY_OUTPUT_FILE}
echo "This dummy file belongs to run ${RUN}, jobid ${JOBSUBJOBID}" >> ${DUMMY_OUTPUT_FILE} 
start_time=$(date +%s)   # start time in seconds 
echo "The job started at: $(date)" >> ${DUMMY_OUTPUT_FILE} 
echo "" >> ${DUMMY_OUTPUT_FILE} 

echo "Args passed from submit script:" >> ${DUMMY_OUTPUT_FILE}
echo "RUN: ${RUN}" >> ${DUMMY_OUTPUT_FILE}
echo "GRIDUSER: ${GRIDUSER}" >> ${DUMMY_OUTPUT_FILE}
echo "GEOFILE: ${GEOFILE}" >> ${DUMMY_OUTPUT_FILE}
echo "USE_LOCAL_GENIE: ${USE_LOCAL_GENIE}" >> ${DUMMY_OUTPUT_FILE}
if [ "$USE_LOCAL_GENIE" = true ]; then
    echo "GTAR: ${GENIE_TAR_NAME}" >> ${DUMMY_OUTPUT_FILE}
    echo "GFOLDER: ${GENIE_FOLDER_NAME}" >> ${DUMMY_OUTPUT_FILE}
fi
echo "" >> ${DUMMY_OUTPUT_FILE} 

echo "Files present in CONDOR_INPUT:" >> ${DUMMY_OUTPUT_FILE} 
ls -lrth $CONDOR_DIR_INPUT >> ${DUMMY_OUTPUT_FILE} 
echo "" >> ${DUMMY_OUTPUT_FILE} 

### Copy input files to GENIE
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/gxspl-FNALsmall.xml .
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/gsimple_flux_${RUN}.root .
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/${GEOFILE} .
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/run_annie_genie.sh .
if [ "$USE_LOCAL_GENIE" = true ]; then
    ${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/${GENIE_TAR_NAME} .
    ${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/Setup_GENIE.sh .
fi

echo "Sleeping for 10s to wait for files to land..." >> ${DUMMY_OUTPUT_FILE} 
sleep 10

EXTRA_ARGS="${RUN} ${DUMMY_OUTPUT_FILE} ${GEOFILE} ${USE_LOCAL_GENIE}"

# un-tar GENIE
if [ "$USE_LOCAL_GENIE" = true ]; then
    tar -xzf ${GENIE_TAR_NAME}
    ls -lrth $GENIE_FOLDER_NAME >> ${DUMMY_OUTPUT_FILE} 
    echo ""
    rm ${GENIE_TAR_NAME}
    EXTRA_ARGS="${RUN} ${DUMMY_OUTPUT_FILE} ${GEOFILE} ${USE_LOCAL_GENIE} ${GENIE_FOLDER_NAME}"
fi

# setup software
singularity exec -B/srv:/srv /cvmfs/singularity.opensciencegrid.org/anniesoft/genie3\:latest/ $CONDOR_DIR_INPUT/rub_the_lamp.sh $EXTRA_ARGS

echo "Moving the output files to CONDOR OUTPUT:" >> ${DUMMY_OUTPUT_FILE}
${JSB_TMP}/ifdh.sh cp -D ./gntp.*.ghep.root ${CONDOR_DIR_OUTPUT}
${JSB_TMP}/ifdh.sh cp -D ./gntp.*.ghep.log.gz ${CONDOR_DIR_OUTPUT}
${JSB_TMP}/ifdh.sh cp -D ./gntp.*.gst.root ${CONDOR_DIR_OUTPUT}
${JSB_TMP}/ifdh.sh cp -D ./BNBFlux*.xml ${CONDOR_DIR_OUTPUT}
${JSB_TMP}/ifdh.sh cp -D ./ANNIE*.xml ${CONDOR_DIR_OUTPUT}
${JSB_TMP}/ifdh.sh cp -D ./pot_*.csv ${CONDOR_DIR_OUTPUT}

echo "" >> ${DUMMY_OUTPUT_FILE}
echo "Input:" >> ${DUMMY_OUTPUT_FILE}
ls $CONDOR_DIR_INPUT >> ${DUMMY_OUTPUT_FILE}
echo "" >> ${DUMMY_OUTPUT_FILE}
echo "Output:" >> ${DUMMY_OUTPUT_FILE}
ls $CONDOR_DIR_OUTPUT >> ${DUMMY_OUTPUT_FILE}

echo "" >> ${DUMMY_OUTPUT_FILE}
echo "Cleaning up..." >> ${DUMMY_OUTPUT_FILE}
echo "srv directory:" >> ${DUMMY_OUTPUT_FILE}
ls -lrth /srv >> ${DUMMY_OUTPUT_FILE}

# make sure to clean up the files left on the worker node
rm /srv/*.root
rm /srv/*.xml
rm /srv/*.log
rm /srv/*.sh
rm /srv/*.gdml
rm /srv/*.status
rm /srv/*.gz
rm /srv/*.csv
if [ -n "${GENIE_FOLDER_NAME}" ]; then
    rm -rf /srv/${GENIE_FOLDER_NAME}/
fi

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