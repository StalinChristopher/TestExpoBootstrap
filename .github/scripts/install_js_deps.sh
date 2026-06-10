#!/usr/bin/env bash
set -euo pipefail
# Usage: install_js_deps.sh [auto|npm|yarn]
PM="${1:-auto}"
if [ "$PM" = "auto" ]; then
  if [ -f "yarn.lock" ]; then
    PM="yarn"
  else
    PM="npm"
  fi
fi
if [ "$PM" = "yarn" ]; then
  corepack enable
  yarn install --frozen-lockfile
else
  npm ci
fi
