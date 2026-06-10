#!/usr/bin/env bash
# Print the path to the main iOS app .bundle under DerivedData Products for a simulator build.
# Usage: ios_find_simulator_app.sh <derived_data_path> <build_configuration>
# Example: ios_find_simulator_app.sh "$GITHUB_WORKSPACE/DerivedDataCI" Debug-Dev
set -euo pipefail

DD="${1:?derived data path}"
BC="${2:?build configuration}"

PRODUCTS="${DD}/Build/Products/${BC}-iphonesimulator"
if [[ ! -d "${PRODUCTS}" ]]; then
  echo "::error::Missing products dir: ${PRODUCTS}" >&2
  if [[ -d "${DD}/Build/Products" ]]; then
    echo "Contents of ${DD}/Build/Products:" >&2
    ls -la "${DD}/Build/Products" >&2 || true
  fi
  exit 1
fi

shopt -s nullglob
candidates=()
for app in "${PRODUCTS}"/*.app; do
  [[ -d "${app}" ]] || continue
  base=$(basename "${app}")
  [[ "${base}" == *UITests* ]] && continue
  candidates+=("${app}")
done

if [[ ${#candidates[@]} -eq 0 ]]; then
  echo "::error::No application .app in ${PRODUCTS}" >&2
  ls -la "${PRODUCTS}" >&2 || true
  exit 1
fi

if [[ ${#candidates[@]} -gt 1 ]]; then
  echo "::warning::Multiple .app bundles; using ${candidates[0]}" >&2
fi

echo "${candidates[0]}"
