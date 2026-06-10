#!/usr/bin/env bash
# Ensure react-native-config env file exists for the given flavor (dev|qa|prod).
# Copies .github/env.<flavor>.ci when the gitignored .env.<flavor> is missing.
set -euo pipefail

FLAVOR="${1:-dev}"
TARGET=".env.${FLAVOR}"
SOURCE=".github/env.${FLAVOR}.ci"

if [ -f "$TARGET" ]; then
  echo "react-native-config: using existing ${TARGET}"
  exit 0
fi

if [ -f "$SOURCE" ]; then
  cp "$SOURCE" "$TARGET"
  echo "react-native-config: created ${TARGET} from ${SOURCE}"
  exit 0
fi

echo "::warning::react-native-config: missing ${TARGET} and no ${SOURCE} — Gradle may lack API_BASE_URL"
