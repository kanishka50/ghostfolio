#!/usr/bin/env bash
# Download every pilot run's artefact and concatenate them into one dataset.
#
# Each run uploads results/measurements.csv holding one row per pipeline stage.
# This script gathers them into experiment/data/measurements-all.csv, which is
# what the analysis reads. Runs already downloaded are skipped, so the script
# can be re-run as more data arrives.
#
# Usage:  bash experiment/collect-results.sh

set -euo pipefail

REPO="kanishka50/ghostfolio"
OUTDIR="experiment/data"
RAWDIR="$OUTDIR/raw"
COMBINED="$OUTDIR/measurements-all.csv"

GH="gh"
command -v gh >/dev/null 2>&1 || GH="/c/Program Files/GitHub CLI/gh.exe"

mkdir -p "$RAWDIR"

echo "Listing successful pilot runs..."
RUN_IDS=$("$GH" run list --repo "$REPO" --limit 200 \
            --json databaseId,conclusion,name \
            --jq '.[] | select(.conclusion == "success") | select(.name | startswith("Pilot -")) | .databaseId')

if [ -z "$RUN_IDS" ]; then
  echo "No successful pilot runs found."
  exit 1
fi

echo "Found $(echo "$RUN_IDS" | wc -l) successful runs."

for id in $RUN_IDS; do
  if [ -d "$RAWDIR/$id" ]; then
    continue                      # already downloaded
  fi
  echo "  downloading run $id"
  mkdir -p "$RAWDIR/$id"
  # Only the result artefact is needed; the .tgz package is not data.
  "$GH" run download "$id" --repo "$REPO" --dir "$RAWDIR/$id" --pattern 'result-*' \
    >/dev/null 2>&1 || echo "    (no result artefact on run $id - skipped)"
done

# Concatenate, keeping exactly one header line.
echo "Combining into $COMBINED ..."
first=1
: > "$COMBINED"
find "$RAWDIR" -name measurements.csv | sort | while read -r f; do
  if [ "$first" = "1" ]; then
    cat "$f" >> "$COMBINED"
    first=0
  else
    tail -n +2 "$f" >> "$COMBINED"
  fi
done

rows=$(( $(wc -l < "$COMBINED") - 1 ))
runs=$(tail -n +2 "$COMBINED" | cut -d, -f2 | sort -u | wc -l)

echo
echo "=============================================="
echo " $rows measurement rows from $runs runs"
echo " -> $COMBINED"
echo "=============================================="
echo
echo "Configurations:"
tail -n +2 "$COMBINED" | cut -d, -f1 | sort | uniq -c
echo
echo "Processors the runs landed on:"
tail -n +2 "$COMBINED" | cut -d, -f4 | sort | uniq -c
