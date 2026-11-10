#!/bin/bash
# Shared worker functions, sourced by every <stage>_job.sh on the grid node (outside the payload container).
# Arguments arrive as key=value (built by mcprod) and become MC_<key> variables, visible inside the container.

mc_parse_args() {
    for kv in "$@"; do
        case "$kv" in *=*) export "MC_${kv%%=*}=${kv#*=}" ;; esac
    done
}

mc_log() { echo "$*" >> "${DUMMY}"; }

mc_start() {
    export WORKDIR=$PWD
    JOBID=${JOBSUBJOBID:-local}
    export DUMMY=${CONDOR_DIR_OUTPUT}/${MC_run}_${JOBID}_dummy_output
    MANIFEST=${CONDOR_DIR_OUTPUT}/${MC_run}_${JOBID}_manifest.json
    START=$(date +%s)
    SITE=${GLIDEIN_Site:-${GLIDEIN_ResourceName:-unknown}}
    IMAGE=$(readlink -f "${MC_container}")
    CPU=$(awk -F': ' '/^model name/ {print $2; exit}' /proc/cpuinfo)
    CPU_FLAGS=$(grep -m1 "^flags" /proc/cpuinfo | tr " " "\n" | grep -E "^(sse4_2|avx|avx2|fma|avx512f)$" | tr "\n" " ")
    FAILED=""
    mc_log "production ${MC_production}  stage ${MC_stage}  run ${MC_run}  test ${MC_test}"
    mc_log "job ${JOBID}  host $(hostname -f)  site ${SITE}  started $(date)"
    mc_log "seed ${MC_seed}  commit ${MC_commit}  config ${MC_config_sha}"
    mc_log "container ${MC_container} -> ${IMAGE}"
    mc_log "cpu ${CPU} (${CPU_FLAGS% })"       # floating-point results can differ between CPU types
    mc_log "arguments: $*"
    mc_log "CONDOR_DIR_INPUT:"
    ls -lh "${CONDOR_DIR_INPUT}" >> "${DUMMY}"
    mc_monitor_start
}

# Peak memory (summed RSS of this job's process tree, KB) and peak disk of the work dir (KB), every 30 s.
mc_monitor_start() {
    PEAKS=${WORKDIR}/.mc_peaks
    echo "0 0" > "${PEAKS}"
    (
        peak_rss=0; peak_disk=0
        while true; do
            rss=$(ps -e -o pid=,ppid=,rss= | awk -v root=$$ '
                { parent[$1] = $2; rss[$1] = $3 }
                END { for (p in parent) { q = p; while (q in parent && q != root && q > 1) q = parent[q]
                                          if (q == root) total += rss[p] }
                      print total + 0 }')
            disk=$(du -sk "${WORKDIR}" 2>/dev/null | cut -f1)
            [ "${rss:-0}" -gt "${peak_rss}" ] && peak_rss=${rss}
            [ "${disk:-0}" -gt "${peak_disk}" ] && peak_disk=${disk}
            echo "${peak_rss} ${peak_disk}" > "${PEAKS}.new" && mv "${PEAKS}.new" "${PEAKS}"
            sleep "${MC_MONITOR_INTERVAL:-30}"
        done
    ) &
    MONITOR_PID=$!
}

mc_stage_in() {
    for name in "$@"; do
        "${JSB_TMP}/ifdh.sh" cp -D "${CONDOR_DIR_INPUT}/${name}" . || mc_log "stage-in FAILED: ${name}"
    done
    sleep "${MC_STAGEIN_WAIT:-10}"   # kept from the validated scripts ("wait for files to land")
}

mc_container() {
    local binds="/srv:/srv"
    case "${WORKDIR}" in /srv|/srv/*) ;; *) binds="${binds},${WORKDIR}:${WORKDIR}" ;; esac
    mc_log "running $* in ${MC_container} ($(date +%T))"
    singularity exec -B "${binds}" "${MC_container}" bash "$@"     # bash: no reliance on +x surviving ifdh
    CONTAINER_EXIT=$?
    mc_log "container exit ${CONTAINER_EXIT} ($(date +%T))"
}

# Required outputs: all must exist, or the job counts as failed. Copied to CONDOR_DIR_OUTPUT (-> -d OUTPUT dir).
mc_outputs() {
    for name in "$@"; do
        if [ -s "${WORKDIR}/${name}" ]; then
            "${JSB_TMP}/ifdh.sh" cp -D "${WORKDIR}/${name}" "${CONDOR_DIR_OUTPUT}"
        else
            FAILED="${FAILED} ${name}"
        fi
    done
}

# Logs: returned when keep_logs=1 (always for GENIE/anniedirt and test jobs), or on failure if keep_failed_logs=1.
mc_logs() {
    if [ "${MC_keep_logs}" = 1 ] || { [ -n "${FAILED}" ] && [ "${MC_keep_failed_logs}" = 1 ]; }; then
        for name in "$@"; do
            [ -e "${WORKDIR}/${name}" ] && "${JSB_TMP}/ifdh.sh" cp -D "${WORKDIR}/${name}" "${CONDOR_DIR_OUTPUT}"
        done
    fi
}

mc_cgroup_peak_mb() {
    local cg file
    cg=$(awk -F: '$1 == "0" { print $3 }' /proc/self/cgroup 2>/dev/null)
    for file in "/sys/fs/cgroup${cg}/memory.peak" /sys/fs/cgroup/memory/memory.max_usage_in_bytes; do
        [ -r "${file}" ] && { echo $(( $(cat "${file}") / 1048576 )); return; }
    done
}

mc_json_files() {                   # name/size list of a directory as JSON
    local dir=$1 first=1 f
    printf '['
    for f in "${dir}"/*; do
        [ -f "${f}" ] || continue
        case "${f}" in *_dummy_output|*_manifest.json) continue ;; esac
        [ ${first} = 1 ] || printf ', '
        printf '{"name": "%s", "bytes": %s}' "$(basename "${f}")" "$(stat -c %s "${f}")"
        first=0
    done
    printf ']'
}

mc_finish() {
    kill "${MONITOR_PID}" 2>/dev/null
    read -r peak_rss peak_disk < "${PEAKS}"
    local wall=$(( $(date +%s) - START )) state=ok exit_code=0 reason=""
    if [ -n "${FAILED}" ]; then
        state=failed; exit_code=4; reason="missing_outputs:$(echo ${FAILED} | tr ' ' ',')"
    fi
    cat > "${MANIFEST}" <<EOF
{"production": "${MC_production}", "stage": "${MC_stage}", "run": ${MC_run}, "test": ${MC_test},
 "status": "${state}", "reason": "${reason}", "jobid": "${JOBID}", "host": "$(hostname -f)", "site": "${SITE}",
 "seed": ${MC_seed}, "commit": "${MC_commit}", "config_sha": "${MC_config_sha}",
 "cpu": "${CPU}", "cpu_flags": "${CPU_FLAGS% }",
 "container": "${MC_container}", "image": "${IMAGE}", "container_exit": ${CONTAINER_EXIT:-null},
 "started": ${START}, "wall_s": ${wall},
 "peak_rss_mb": $(( peak_rss / 1024 )), "peak_disk_mb": $(( peak_disk / 1024 )), "cgroup_peak_mb": "$(mc_cgroup_peak_mb)",
 "inputs": $(mc_json_files "${CONDOR_DIR_INPUT}"), "outputs": $(mc_json_files "${CONDOR_DIR_OUTPUT}")}
EOF
    mc_log "peak memory $(( peak_rss / 1024 )) MB, peak disk $(( peak_disk / 1024 )) MB, wall ${wall} s"
    mc_log "CONDOR_DIR_OUTPUT:"
    ls -lh "${CONDOR_DIR_OUTPUT}" >> "${DUMMY}"
    mc_log "ended $(date)"
    if [ "${state}" = ok ]; then
        mc_log "MCPROD_STATUS=ok"
        mc_log "DONE"
    else
        mc_log "MCPROD_STATUS=failed exit=${exit_code} reason=${reason}"
    fi
    exit ${exit_code}
}
