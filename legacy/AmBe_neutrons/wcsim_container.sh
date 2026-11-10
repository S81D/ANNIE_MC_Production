#!/bin/bash 
# James Minock 

# execute WCSim events on the grid

PART_NAME=$1

# logfile
touch /srv/logfile_${PART_NAME}.txt 
echo "pwd:" >> /srv/logfile_${PART_NAME}.txt
pwd >> /srv/logfile_${PART_NAME}.txt
echo "" >> /srv/logfile_${PART_NAME}.txt

echo "sourcing script:" >> /srv/logfile_${PART_NAME}.txt
echo "" >> /srv/logfile_${PART_NAME}.txt

# source setup script
source sourceme >> /srv/logfile_${PART_NAME}.txt
chmod +x WCSim

echo "" >> /srv/logfile_${PART_NAME}.txt

echo "running WCSim..." >> /srv/logfile_${PART_NAME}.txt

# Run the toolchain, and output verbose to log file 
./WCSim WCSim.mac >> /srv/logfile_${PART_NAME}.txt

echo "" >> /srv/logfile_${PART_NAME}.txt
echo "-----------------------------------------" >> /srv/logfile_${PART_NAME}.txt 
echo "Finished!" >> /srv/logfile_${PART_NAME}.txt 

# log files
echo "" >> /srv/logfile_${PART_NAME}.txt
echo "WCSim directory contents:" >> /srv/logfile_${PART_NAME}.txt
ls -lrth >> /srv/logfile_${PART_NAME}.txt
echo "" >> /srv/logfile_${PART_NAME}.txt

# copy any produced files to /srv for extraction
cp wcsim_0.root /srv/wcsim_${PART_NAME}.root 
#cp wcsim_lappd_0.root /srv/wcsim_lappd_${PART_NAME}.root

# make sure any output files you want to keep are put in /srv or any subdirectory of /srv 

### END ###
