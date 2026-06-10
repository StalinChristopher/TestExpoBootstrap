#!/usr/bin/env bash
# Copy committed CI env templates into gitignored flavor .env files before native builds.
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "${ROOT}"

copy_env() {
  local src="$1"
  local dest="$2"
  if [[ ! -f "${src}" ]]; then
    echo "::warning::CI env template missing: ${src}"
    return 0
  fi
  cp "${src}" "${dest}"
  echo "Restored ${dest} from ${src}"
}

copy_env ".github/env.dev.ci" ".env.dev"
