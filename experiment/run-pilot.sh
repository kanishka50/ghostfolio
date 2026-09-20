#!/usr/bin/env bash
# Dispatch the Config A / Config B pilot pair, STRICTLY ONE RUN AT A TIME.
#
# Two properties this script exists to guarantee:
#   1. SERIAL EXECUTION. Concurrent runs would share GitHub's infrastructure
#      and contaminate each other's measurements, so each run is watched to
#      completion before the next is dispatched.
#   2. RANDOMISED ORDER FROM A FIXED SEED. If configurations ran in a fixed
#      A,B,A,B order, any drift in GitHub's runner fleet over the collection
#      window would align with configuration and be indistinguishable from a
#      treatment effect. The order is shuffled, and the seed is recorded so the
#      schedule is reproducible.
#
# Usage:  bash experiment/run-pilot.sh [REPLICATES] [SEED]
#         bash experiment/run-pilot.sh 10 20260916

set -euo pipefail

REPO="kanishka50/ghostfolio"
REPLICATES="${1:-10}"
SEED="${2:-20260920}"

GH="gh"
command -v gh >/dev/null 2>&1 || GH="/c/Program Files/GitHub CLI/gh.exe"

# Build the schedule: REPLICATES of each config, shuffled from the fixed seed.
SCHEDULE=$(
  {
    for _ in $(seq 1 "$REPLICATES"); do echo A; echo B; done
  } | shuf --random-source=<(yes "$SEED")
)

TOTAL=$(echo "$SCHEDULE" | wc -l)

echo "=============================================="
echo " Green DevOps pilot - variance measurement"
echo "=============================================="
echo "Repository : $REPO"
echo "Replicates : $REPLICATES per configuration"
echo "Seed       : $SEED"
echo "Total runs : $TOTAL (serial, ~8 min each)"
echo
echo "Schedule   : $(echo "$SCHEDULE" | tr '\n' ' ')"
echo

n=0
for cfg in $SCHEDULE; do
  n=$((n + 1))
  wf="pilot-config-$(echo "$cfg" | tr '[:upper:]' '[:lower:]').yml"

  echo "----------------------------------------------"
  echo "[$n/$TOTAL] Dispatching Config $cfg ($wf)"

  "$GH" workflow run "$wf" --repo "$REPO"

  # The run needs a moment to be registered before its ID can be read back.
  sleep 8
  run_id=$("$GH" run list --repo "$REPO" --workflow "$wf" --limit 1 \
             --json databaseId --jq '.[0].databaseId')

  echo "[$n/$TOTAL] Run $run_id started - waiting for it to finish"

  # --exit-status makes a failed run fail this script, so a broken harness
  # stops collection immediately instead of producing unusable rows.
  if ! "$GH" run watch "$run_id" --repo "$REPO" --exit-status >/dev/null 2>&1; then
    echo
    echo "!! Run $run_id FAILED. Stopping so the cause can be investigated"
    echo "!! before more runs are collected."
    echo "!! Inspect with: gh run view $run_id --repo $REPO --log-failed"
    exit 1
  fi

  echo "[$n/$TOTAL] Config $cfg complete (run $run_id)"
done

echo
echo "=============================================="
echo " All $TOTAL runs complete."
echo " Collect them with: bash experiment/collect-results.sh"
echo "=============================================="
