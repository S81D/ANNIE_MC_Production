#!/usr/bin/env bash

RUN=$1
DUMMYFILE=$2
GEOFILE=$3
USE_LOCAL_GENIE=$4
if [ "$USE_LOCAL_GENIE" = true ]; then
    GENIE_FOLDER_NAME=$5
    source /srv/Setup_GENIE.sh ${GENIE_FOLDER_NAME}
else
    source /Genie/GENIE-v3-master/annie/Setup_GENIE.sh
fi

echo "" >> ${DUMMYFILE} 
echo "Executing rub_the_lamp.sh..." >> ${DUMMYFILE} 
echo "" >> ${DUMMYFILE} 

which gevgen_fnal >> ${DUMMYFILE} 

chmod +x run_annie_genie.sh

./run_annie_genie.sh \
  -o . \
  -r ${RUN} \
  -n 20000 \
  -f gsimple_flux_${RUN}.root \
  -x gxspl-FNALsmall.xml \
  -g ${GEOFILE} \
  --seed ${RUN} \
  --topvol WORLD_LV \
  --tune G18_10a_02_11a

echo "" >> ${DUMMYFILE} 
echo "Your wish is granted" >> ${DUMMYFILE} 
echo "" >> ${DUMMYFILE} 

# can convert into a flattree
gntpc -i gntp.${RUN}.ghep.root -f gst -o gntp.${RUN}.gst.root
echo "Flat tree created!" >> ${DUMMYFILE} 
echo "" >> ${DUMMYFILE}

# scrape POT normalization before compressing the log
POT=$(grep "Normalization for generated sample" gntp.${RUN}.ghep.log | awk '{print $6}')
echo "${RUN},${POT}" > pot_${RUN}.csv
echo "POT for run ${RUN}: ${POT}" >> ${DUMMYFILE}
echo "" >> ${DUMMYFILE}

# we can compress the log file to reduce the storage impact
gzip -9 gntp.*.ghep.log
echo ".ghep.log compressed" >> ${DUMMYFILE}