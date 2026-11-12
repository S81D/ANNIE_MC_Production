#!/bin/bash
# ============================================================
# find_broken_rootfiles.sh
#
# Identify broken ANNIE MC ROOT files by checking for the required
# TTrees via rootls (default: phaseIITriggerTree, phaseIITankClusterTree,
# phaseIIMRDClusterTree; --trees overrides, e.g. for toolchains that do not
# fill a tree, or the newer single-tree output, which this default will flag).
# Writes the list of broken files to a .txt file for later
# deletion (via delete_broken_rootfiles.sh outside the container).
#
# Speed optimization: only opens files whose size falls more
# than N sigma below the mean (Gaussian pre-filter on stat()).
#
# Usage:
#   ./find_broken_rootfiles.sh /path/to/root/files/
#   ./find_broken_rootfiles.sh /path/to/root/files/ --sigma 1.5
#   ./find_broken_rootfiles.sh /path/to/root/files/ --check-all
#   ./find_broken_rootfiles.sh /path/to/root/files/ --output my_list.txt
#   ./find_broken_rootfiles.sh /path/to/root/files/ --trees "wcsimT wcsimGeoT" --pattern "wcsim_[0-9]*.root"
# ============================================================

set -euo pipefail

REQUIRED_TREES=("phaseIITriggerTree" "phaseIITankClusterTree" "phaseIIMRDClusterTree")
PATTERN="MC_*.root"
SIGMA=1.0
CHECK_ALL=false
OUTPUT="broken_files.txt"

# ---- Parse arguments ----
DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sigma)     SIGMA="$2"; shift 2 ;;
        --check-all) CHECK_ALL=true; shift ;;
        --pattern)   PATTERN="$2"; shift 2 ;;
        --trees)     read -r -a REQUIRED_TREES <<< "$2"; shift 2 ;;
        --output|-o) OUTPUT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 DIRECTORY [--sigma N] [--check-all] [--pattern GLOB] [--trees \"T1 T2\"] [--output FILE]"
            exit 0 ;;
        *)
            if [[ -z "$DIR" ]]; then
                DIR="$1"
            else
                echo "Unknown argument: $1" >&2; exit 1
            fi
            shift ;;
    esac
done

if [[ -z "$DIR" ]]; then
    echo "Usage: $0 DIRECTORY [--sigma N] [--check-all] [--pattern GLOB] [--output FILE]"
    exit 1
fi

# Verify rootls is available
if ! command -v rootls &>/dev/null; then
    echo "ERROR: rootls not found. Set up ROOT first (in the toolanalysis image: source /usr/local/bin/thisroot.sh)." >&2
    exit 1
fi

# ---- Collect files and sizes ----
shopt -s nullglob
FILES=("${DIR%/}"/$PATTERN)
shopt -u nullglob

NFILES=${#FILES[@]}
if [[ $NFILES -eq 0 ]]; then
    echo "No files matching '${DIR%/}/$PATTERN' found."
    exit 0
fi

# Get sizes in bytes via stat, compute mean/std with awk
declare -a SIZES_BYTES
for f in "${FILES[@]}"; do
    SIZES_BYTES+=("$(stat -c%s "$f")")
done

# Awk computes mean, std, threshold in MB and prints them
read -r MEAN STD THRESHOLD < <(
    printf '%s\n' "${SIZES_BYTES[@]}" | awk -v sigma="$SIGMA" '
    {
        mb = $1 / (1024*1024)
        s[NR] = mb
        sum += mb
    }
    END {
        mean = sum / NR
        var = 0
        for (i = 1; i <= NR; i++) var += (s[i] - mean)^2
        std = sqrt(var / NR)
        thresh = mean - sigma * std
        printf "%.4f %.4f %.4f\n", mean, std, thresh
    }'
)

echo "Found $NFILES file(s) in $DIR"
echo "  Size distribution:  mean = ${MEAN} MB,  std = ${STD} MB"
echo "  Threshold (mean - ${SIGMA}σ) = ${THRESHOLD} MB"

# Degenerate case: all files ~same size
if awk "BEGIN { exit ($STD < 0.01) ? 0 : 1 }"; then
    echo "  [!] Very low variance — falling back to --check-all."
    CHECK_ALL=true
fi

# ---- Partition into check vs skip ----
declare -a TO_CHECK=()
NSKIPPED=0

for i in "${!FILES[@]}"; do
    size_mb=$(awk "BEGIN { printf \"%.4f\", ${SIZES_BYTES[$i]} / (1024*1024) }")
    if $CHECK_ALL || awk "BEGIN { exit ($size_mb < $THRESHOLD) ? 0 : 1 }"; then
        TO_CHECK+=("${FILES[$i]}")
    else
        ((NSKIPPED++)) || true
    fi
done

echo ""
if $CHECK_ALL; then
    echo "  Checking all ${#TO_CHECK[@]} file(s) ..."
else
    echo "  Skipping $NSKIPPED file(s) above threshold (presumed good)"
    echo "  Checking ${#TO_CHECK[@]} file(s) below threshold ..."
fi
echo ""

# ---- TTree validation via rootls ----
declare -a BROKEN=()
NGOOD=0

for filepath in "${TO_CHECK[@]}"; do
    basename="$(basename "$filepath")"
    size_mb=$(awk "BEGIN { printf \"%.1f\", $(stat -c%s "$filepath") / (1024*1024) }")

    # rootls lists keys in the file; check for required trees
    listing=$(rootls "$filepath" 2>/dev/null) || listing=""

    missing=()
    for tree in "${REQUIRED_TREES[@]}"; do
        if ! echo "$listing" | grep -q "$tree"; then
            missing+=("$tree")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        ((NGOOD++)) || true
        printf "  OK      %20s  (%s MB)\n" "$basename" "$size_mb"
    else
        BROKEN+=("$filepath")
        printf "  BROKEN  %20s  (%s MB)  -- missing: %s\n" \
            "$basename" "$size_mb" "${missing[*]}"
    fi
done

# ---- Summary ----
echo ""
echo "============================================================"
echo "  Total files:    $NFILES"
echo "  Presumed good:  $NSKIPPED  (above ${THRESHOLD} MB)"
echo "  Checked:        ${#TO_CHECK[@]}"
echo "    Passed:       $NGOOD"
echo "    Broken:       ${#BROKEN[@]}"
echo "============================================================"

if [[ ${#BROKEN[@]} -eq 0 ]]; then
    echo "No broken files found. No output file written."
    exit 0
fi

# ---- Write broken file list ----
: > "$OUTPUT"
for fpath in "${BROKEN[@]}"; do
    echo "$fpath" >> "$OUTPUT"
done

echo ""
echo "Wrote ${#BROKEN[@]} broken file path(s) to: $OUTPUT"
echo "Run delete_broken_rootfiles.sh $OUTPUT (outside the container) to remove them."
