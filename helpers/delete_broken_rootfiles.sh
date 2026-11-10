#!/bin/bash
# ============================================================
# delete_broken_rootfiles.sh
#
# Delete files listed in a .txt file (one path per line) using
# `ifdh rm`. Intended to be run OUTSIDE the container, after
# find_broken_rootfiles.sh has produced the list.
#
# Usage:
#   ./delete_broken_rootfiles.sh broken_files.txt
#   ./delete_broken_rootfiles.sh broken_files.txt --no-confirm
# ============================================================

set -uo pipefail

NO_CONFIRM=false
LIST=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-confirm) NO_CONFIRM=true; shift ;;
        -h|--help)
            echo "Usage: $0 LIST.txt [--no-confirm]"
            exit 0 ;;
        *)
            if [[ -z "$LIST" ]]; then
                LIST="$1"
            else
                echo "Unknown argument: $1" >&2; exit 1
            fi
            shift ;;
    esac
done

if [[ -z "$LIST" ]]; then
    echo "Usage: $0 LIST.txt [--no-confirm]" >&2
    exit 1
fi

if [[ ! -f "$LIST" ]]; then
    echo "ERROR: file not found: $LIST" >&2
    exit 1
fi

if ! command -v ifdh &>/dev/null; then
    echo "ERROR: ifdh not found. Set it up first (e.g. 'setup ifdhc')." >&2
    exit 1
fi

# Read non-empty, non-comment lines
mapfile -t FILES < <(grep -Ev '^\s*(#|$)' "$LIST")
NFILES=${#FILES[@]}

if [[ $NFILES -eq 0 ]]; then
    echo "No files listed in $LIST. Nothing to do."
    exit 0
fi

echo "About to remove $NFILES file(s) listed in $LIST:"
for fpath in "${FILES[@]}"; do
    echo "  $fpath"
done

if ! $NO_CONFIRM; then
    echo ""
    read -rp "Proceed? [y/N]: " answer
    if [[ "${answer,,}" != "y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

NOK=0
NFAIL=0
for fpath in "${FILES[@]}"; do
    if ifdh rm "$fpath"; then
        echo "  Removed: $fpath"
        ((NOK++)) || true
    else
        echo "  FAILED : $fpath" >&2
        ((NFAIL++)) || true
    fi
done

echo ""
echo "Done. Removed $NOK / $NFILES file(s).  Failures: $NFAIL"
[[ $NFAIL -eq 0 ]]
