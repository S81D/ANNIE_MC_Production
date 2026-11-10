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
echo "" >> ${DUMMY_OUTPUT_FILE} 

echo "Files present in CONDOR_INPUT:" >> ${DUMMY_OUTPUT_FILE} 
ls -lrth $CONDOR_DIR_INPUT >> ${DUMMY_OUTPUT_FILE} 
echo "" >> ${DUMMY_OUTPUT_FILE} 

### Copy input files
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/gdml.tar.gz .
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/gntp.${RUN}.ghep.root .
${JSB_TMP}/ifdh.sh cp -D $CONDOR_DIR_INPUT/${GEOFILE} .

echo "Sleeping for 10s to wait for files to land..." >> ${DUMMY_OUTPUT_FILE} 
sleep 10

# un-tar gdml
tar -xzf gdml.tar.gz
ls -lrth *.xsd >> ${DUMMY_OUTPUT_FILE} 
echo ""
rm gdml.tar.gz

# setup software
singularity exec -B/srv:/srv /cvmfs/singularity.opensciencegrid.org/anniesoft/g4dirt\:latest/ $CONDOR_DIR_INPUT/run_g4dirt_container.sh $RUN ${DUMMY_OUTPUT_FILE} ${GEOFILE}

echo "Moving the output files to CONDOR OUTPUT:" >> ${DUMMY_OUTPUT_FILE}
${JSB_TMP}/ifdh.sh cp -D ./annie_tank_flux.*.root ${CONDOR_DIR_OUTPUT}
${JSB_TMP}/ifdh.sh cp -D ./annie_tank_flux.*.log.gz ${CONDOR_DIR_OUTPUT}

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
rm /srv/*.log
rm /srv/*.sh
rm /srv/*.gdml
rm /srv/*.gz
rm /srv/*.xsd

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