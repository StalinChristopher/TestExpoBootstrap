#!/usr/bin/env bash
# Distribute a binary via Firebase App Distribution CLI and emit tester + console URLs
# to GITHUB_OUTPUT (testing_uri, firebase_console_uri).
#
# Required env:
#   GOOGLE_APPLICATION_CREDENTIALS  path to service account JSON
#   FIREBASE_APP_ID                 Firebase app ID
#   DISTRIBUTE_FILE                 APK or IPA path
#   GROUPS                          comma-separated tester groups
#
# Optional env:
#   RELEASE_NOTES
set -euo pipefail

if [[ -z "${GITHUB_OUTPUT:-}" ]]; then
  echo "::error::GITHUB_OUTPUT is not set (run from a GitHub Actions step)."
  exit 1
fi

for var in GOOGLE_APPLICATION_CREDENTIALS FIREBASE_APP_ID DISTRIBUTE_FILE GROUPS; do
  if [[ -z "${!var:-}" ]]; then
    echo "::error::${var} is required."
    exit 1
  fi
done

if [[ ! -f "${DISTRIBUTE_FILE}" ]]; then
  echo "::error::DISTRIBUTE_FILE not found: ${DISTRIBUTE_FILE}"
  exit 1
fi

log="${RUNNER_TEMP:-/tmp}/firebase-appdistribution.log"
CMD=(npx --yes firebase-tools@13 appdistribution:distribute "${DISTRIBUTE_FILE}" --app "${FIREBASE_APP_ID}" --groups "${GROUPS}")
if [[ -n "${RELEASE_NOTES:-}" ]]; then
  CMD+=(--release-notes "${RELEASE_NOTES}")
fi

set +e
"${CMD[@]}" 2>&1 | tee "${log}"
firebase_exit="${PIPESTATUS[0]}"
set -e

if [[ "${firebase_exit}" -ne 0 ]]; then
  echo "::error::Firebase App Distribution failed with exit code ${firebase_exit}"
  echo "--- Last 50 lines of Firebase CLI log ---"
  tail -n 50 "${log}" || true
  exit "${firebase_exit}"
fi

# Firebase prints URLs like https://appdistribution.firebase.google.com/... (host starts
# right after https://). The old pattern required extra characters before the hostname and
# never matched, so Slack fell back to the GitHub artifact link on iOS.
testing_uri="$(grep -Eo 'https://appdistribution\.firebase\.google\.com[^[:space:]"<>]*' "${log}" | head -n 1 || true)"
firebase_console_uri="$(grep -Eo 'https://console\.firebase\.google\.com[^[:space:]"<>]*' "${log}" | head -n 1 || true)"

{
  echo "testing_uri=${testing_uri}"
  echo "firebase_console_uri=${firebase_console_uri}"
} >> "${GITHUB_OUTPUT}"

if [[ -n "${testing_uri}" ]]; then
  echo "Firebase App Distribution testing URL: ${testing_uri}"
else
  echo "::warning::Firebase distribute finished but no tester install URL was parsed from CLI output; Slack will fall back to the GitHub artifact link."
fi
if [[ -n "${firebase_console_uri}" ]]; then
  echo "Firebase console URL: ${firebase_console_uri}"
fi
