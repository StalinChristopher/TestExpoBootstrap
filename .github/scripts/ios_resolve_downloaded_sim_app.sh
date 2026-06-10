#!/usr/bin/env bash
# Find a simulator .app after actions/download-artifact (supports staged dirs and .zip).
# Usage: ios_resolve_downloaded_sim_app.sh <search_root>
set -euo pipefail

ROOT="${1:?search root}"
if [[ ! -d "${ROOT}" ]]; then
  echo "::error::Search root does not exist: ${ROOT}" >&2
  exit 1
fi

# Unzip any archives produced by upload-artifact / manual zip staging.
shopt -s nullglob
for zip in "${ROOT}"/*.zip; do
  dest="${ROOT}/$(basename "${zip}" .zip)-extracted"
  mkdir -p "${dest}"
  unzip -q -o "${zip}" -d "${dest}"
done

shopt -s nullglob
apps=()
while IFS= read -r -d '' app; do
  base=$(basename "${app}")
  [[ "${base}" == *UITests* ]] && continue
  apps+=("${app}")
done < <(find "${ROOT}" -type d -name '*.app' -print0 2>/dev/null)

if [[ ${#apps[@]} -eq 0 ]]; then
  echo "::error::No .app bundle under ${ROOT}" >&2
  echo "Directory listing:" >&2
  find "${ROOT}" -maxdepth 6 \( -type d -o -type f \) 2>/dev/null | head -60 >&2 || true
  exit 1
fi

if [[ ${#apps[@]} -gt 1 ]]; then
  echo "::warning::Multiple .app bundles; using ${apps[0]}" >&2
fi

echo "${apps[0]}"
