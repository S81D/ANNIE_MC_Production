# Run MC toolchains on the grid
# Author: Steven Doran

import os
import time
import re
import subprocess

#
#
#

'''@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@'''

''' Please modify the following to reflect your working directory '''

wcsim_file_path = '/pnfs/annie/scratch/users/doran/output/genie_muons/pmt_tilting_dirt_QE_1.50_HM_1.50_2/'     # wcsim root files from the grid

# from previous jobs
events_per_job = 500    # match wcsim root jobs
N_jobs = 1000           # total number of jobs sent / present

# for current grid submission
files_per_job = 500
J = N_jobs

# Pattern to extract Ni, Nf, M
file_pattern = re.compile(r"wcsim_(\d+)_(\d+)_(\d+)\.root")

# Path to the submission script
submission_script = "./submit_grid_job.sh"

# make sure to run: chmod +x submit_grid_job.sh  prior to executing this script

'''@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@'''

#
#
#
#
#

# file structure:
#      wcsim_Ni_Nf_M.root
#          Ni runs from 0 to 499499
#          Nf runs from 499 to 499999
#          M runs from 0 to 499

# first one: 0_499
# last one: 499500_499999


print('\nTime to scan!\n')

# Efficiently scan the directory and cache valid filenames
valid_files = []

with os.scandir(wcsim_file_path) as entries:
    count = 0
    for entry in entries:
        if entry.is_file() and entry.name.endswith(".root"):
            match = file_pattern.match(entry.name)
            if match:
                full_path = os.path.join(wcsim_file_path, entry.name)
                valid_files.append(full_path)
                count += 1
                if count % 10000 == 0:
                    print(f"Scanned {count} files...")

# Sort files by Ni (optional but helpful for reproducibility)
def sort_key(f):
    match = file_pattern.search(os.path.basename(f))
    return int(match.group(1)) if match else 0

valid_files.sort(key=sort_key)

print('\nSubmitting jobs...\n')

# Batch into J jobs
for job_id in range(J):
    start_idx = job_id * files_per_job
    end_idx = start_idx + files_per_job
    file_batch = valid_files[start_idx:end_idx]

    if not file_batch:
        break

    # Construct environment variable for processed files path
    env = os.environ.copy()
    env["PROCESSED_FILES_PATH"] = ":".join(file_batch)

    # You can also pass a RUN number or other identifier here
    run_label = f"{job_id}"

    # Call submission script
    print(f"Submitting job {job_id} with {len(file_batch)} files")
    subprocess.run([submission_script, run_label], env=env)



# finish up
print('\nAll jobs sent!\n')
time.sleep(1)
print('Exiting...\n')
