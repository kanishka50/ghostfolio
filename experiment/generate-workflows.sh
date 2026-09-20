#!/usr/bin/env bash
# Generate the pilot workflows from experiment/workflow-template.yml.
#
# The point of generating them is that Config A and Config B then CANNOT differ
# in anything except the single line this script substitutes. Editing the
# generated files by hand defeats that guarantee - edit the template instead.
#
# Usage:  bash experiment/generate-workflows.sh

set -euo pipefail

TEMPLATE="experiment/workflow-template.yml"
OUT=".github/workflows"
mkdir -p "$OUT"

gen() { # gen <ID> <name> <cache line>
  local id="$1" name="$2" cache="$3"
  local out="$OUT/pilot-config-$(echo "$id" | tr '[:upper:]' '[:lower:]').yml"
  {
    echo "# GENERATED FILE - do not edit. Source: $TEMPLATE"
    echo "# Regenerate with: bash experiment/generate-workflows.sh"
    sed -e "s/@@CONFIG@@/$id/g" \
        -e "s/@@CONFIG_NAME@@/$name/g" \
        -e "s|@@CACHE_LINE@@|$cache|" \
        "$TEMPLATE"
  } > "$out"
  echo "wrote $out"
}

# Config A: the uncached baseline. No `cache:` key at all.
gen A "Full, uncached" "          # NO \`cache:\` key here. Config A is the UNCACHED baseline."

# Config B: identical but for this one line - THE VARIABLE UNDER TEST.
gen B "Full, cached"   "          # THE SINGLE VARIABLE under test.\n          cache: 'npm'"

# The two files must differ only in the config identifier and the cache line.
echo
echo "Difference between the generated workflows:"
diff "$OUT/pilot-config-a.yml" "$OUT/pilot-config-b.yml" || true
