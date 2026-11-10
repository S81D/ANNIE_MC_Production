#!/usr/bin/env bash

RUN=$1
DUMMYFILE=$2
GEOFILE=$3

# Assumes you are using the official container-bundled anniedirt installation
chmod -x /home/run_g4dirt.sh

echo "" >> ${DUMMYFILE} 
echo "Executing run_g4dirt.sh..." >> ${DUMMYFILE} 
echo "" >> ${DUMMYFILE} 

source /home/run_g4dirt.sh \
    -r=${RUN} \
    -i=. \
    -n=20000 \
    -g=${GEOFILE} \
    -o=.

echo "Finished!" >> ${DUMMYFILE}
echo "" >> ${DUMMYFILE}

# we can compress the log file to reduce the storage impact
gzip -9 annie_tank_flux.*.log
echo ".log compressed" >> ${DUMMYFILE}
echo "" >> ${DUMMYFILE}

ls -lrth >> ${DUMMYFILE}