#!/bin/bash
# Sum the GENIE POT (pot_N.csv) over the runs whose files are present in a directory.
# Usage: ./read_MC_POT.sh <file_dir> <csv_dir> [pattern]   (pattern default MC_*.root; GENIE: gntp.*.ghep.root)

MC_DIR="${1:?Usage: $0 <file_dir> <csv_dir> [pattern]}"
CSV_DIR="${2:?Usage: $0 <file_dir> <csv_dir> [pattern]}"
PATTERN="${3:-MC_*.root}"
PREFIX="${PATTERN%%\**}"     # text before the *  (run number = what the * matches)
SUFFIX="${PATTERN#*\*}"      # text after the *

pot_list=$(mktemp)
missing_list=()
n_files=0

for mc_file in "$MC_DIR"/$PATTERN; do
    [ -e "$mc_file" ] || {
        echo "No $PATTERN files in $MC_DIR"
        rm -f "$pot_list"
        exit 1
    }

    base=$(basename "$mc_file")
    N="${base#"$PREFIX"}"
    N="${N%"$SUFFIX"}"
    csv_file="$CSV_DIR/pot_${N}.csv"

    if [ ! -f "$csv_file" ]; then
        missing_list+=("$N")
        continue
    fi

    pot=$(awk -F',' 'NR==1 {
        gsub(/[[:space:]]/, "", $2)
        print $2
        exit
    }' "$csv_file")

    # Accept ordinary or scientific-notation numeric POT values only.
    if [[ ! "$pot" =~ ^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$ ]]; then
        echo "WARN: could not parse a numeric POT from $csv_file" >&2
        missing_list+=("$N")
        continue
    fi

    printf "  N=%-6s  POT=%s\n" "$N" "$pot"
    echo "$pot" >> "$pot_list"
    n_files=$((n_files + 1))
done

# Sum valid POT values in one pass.
total_pot=$(awk '{s += $1} END {printf "%.6e\n", s}' "$pot_list")
rm -f "$pot_list"

missing_count=${#missing_list[@]}

echo "----------------------------------------"
echo "Files summed       : $n_files"
echo "Missing POT files  : $missing_count"

if [ "$missing_count" -gt 0 ]; then
    # Sort numerically for readability.
    sorted_missing=$(printf '%s\n' "${missing_list[@]}" | sort -n | tr '\n' ' ')
    echo "Missing N          : $sorted_missing"
fi

echo "Total POT          : $total_pot"

if [ "$n_files" -gt 0 ]; then
    read -r avg_pot missing_pot corrected_pot < <(
        awk -v total="$total_pot" -v n="$n_files" -v missing="$missing_count" '
            BEGIN {
                avg = total / n
                estimated_missing = avg * missing
                corrected = total + estimated_missing
                printf "%.6e %.6e %.6e\n", avg, estimated_missing, corrected
            }'
    )

    echo "Average POT/file  : $avg_pot"
    echo "Estimated missing : $missing_pot"
    echo "Corrected POT     : $corrected_pot"
else
    echo "ERROR: no valid POT files were found; cannot estimate missing POT." >&2
    exit 1
fi
