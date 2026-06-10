#!/usr/bin/env bash
# POST internal-build summary to Slack Workflow Builder webhook trigger.
#
# Slack setup: create a Workflow with a Webhook trigger and one Text variable named
# "message" (not "text"). Set repository secret SLACK_TRIGGER_WEBHOOK_URL to the
# trigger URL.
#
# Optional BUILD_* environment variables (workflows set these before calling):
#   BUILD_PLATFORM              android | ios
#   BUILD_FLAVOR                dev | dist
#   BUILD_CHANNEL               firebase | play-internal
#   BUILD_VERSION_NAME          marketing version (e.g. 1.4.0)
#   BUILD_VERSION_CODE          Android versionCode
#   BUILD_BUILD_NUMBER          iOS CFBundleVersion
#   BUILD_GRADLE_TASK           Android Gradle task name
#   BUILD_IOS_SCHEME            iOS Xcode scheme
#   BUILD_REF                   branch or ref built
#   BUILD_WORKFLOW_URL          link to the GitHub Actions run
#   BUILD_ARTIFACT_NAME         workflow artifact name
#   BUILD_ARTIFACT_URL          signed download URL for the artifact ZIP
#   BUILD_RELEASE_NOTES         release notes for testers
#   BUILD_APP_DISTRIBUTION_TESTING_URL   Firebase tester / install link
#   BUILD_APP_DISTRIBUTION_CONSOLE_URL   Firebase console release link
#   BUILD_INTERNAL_SHARING_URL           Play Internal App Sharing link
set -euo pipefail

append_metadata_lines() {
  local platform="${BUILD_PLATFORM:-}"
  local flavor="${BUILD_FLAVOR:-}"
  local channel="${BUILD_CHANNEL:-}"
  local version_name="${BUILD_VERSION_NAME:-}"
  local version_code="${BUILD_VERSION_CODE:-}"
  local build_number="${BUILD_BUILD_NUMBER:-}"
  local gradle_task="${BUILD_GRADLE_TASK:-}"
  local ios_scheme="${BUILD_IOS_SCHEME:-}"
  local ref="${BUILD_REF:-}"
  local workflow_url="${BUILD_WORKFLOW_URL:-}"

  if [[ -n "${platform}" ]]; then
    local platform_label
    case "${platform}" in
      android) platform_label="Android" ;;
      ios) platform_label="iOS" ;;
      *) platform_label="${platform}" ;;
    esac
    BUILD_NOTIFY_LINES+=("Platform: ${platform_label}")
  fi

  if [[ -n "${flavor}" ]]; then
    BUILD_NOTIFY_LINES+=("Flavor: ${flavor}")
  fi

  if [[ -n "${channel}" ]]; then
    local channel_label
    case "${channel}" in
      firebase) channel_label="Firebase App Distribution" ;;
      play-internal) channel_label="Play Internal App Sharing" ;;
      *) channel_label="${channel}" ;;
    esac
    BUILD_NOTIFY_LINES+=("Channel: ${channel_label}")
  fi

  if [[ -n "${version_name}" ]]; then
    if [[ -n "${version_code}" ]]; then
      BUILD_NOTIFY_LINES+=("Version: ${version_name} (${version_code})")
    elif [[ -n "${build_number}" ]]; then
      BUILD_NOTIFY_LINES+=("Version: ${version_name} (${build_number})")
    else
      BUILD_NOTIFY_LINES+=("Version: ${version_name}")
    fi
  elif [[ -n "${version_code}" ]]; then
    BUILD_NOTIFY_LINES+=("Version code: ${version_code}")
  elif [[ -n "${build_number}" ]]; then
    BUILD_NOTIFY_LINES+=("Build number: ${build_number}")
  fi

  if [[ -n "${gradle_task}" ]]; then
    BUILD_NOTIFY_LINES+=("Gradle task: ${gradle_task}")
  fi

  if [[ -n "${ios_scheme}" ]]; then
    BUILD_NOTIFY_LINES+=("Scheme: ${ios_scheme}")
  fi

  if [[ -n "${ref}" ]]; then
    BUILD_NOTIFY_LINES+=("Branch: ${ref}")
  fi

  if [[ -n "${workflow_url}" ]]; then
    BUILD_NOTIFY_LINES+=("Workflow: ${workflow_url}")
  fi
}

append_distribution_lines() {
  local platform="${BUILD_PLATFORM:-}"
  local artifact="${BUILD_ARTIFACT_NAME:-}"
  local artifact_url="${BUILD_ARTIFACT_URL:-}"
  local fad_testing="${BUILD_APP_DISTRIBUTION_TESTING_URL:-}"
  local fad_console="${BUILD_APP_DISTRIBUTION_CONSOLE_URL:-}"
  local play_internal_sharing="${BUILD_INTERNAL_SHARING_URL:-}"

  local bundle_kind="APK"
  if [[ "${platform}" == "ios" ]]; then
    bundle_kind="IPA"
  fi

  if [[ -n "${fad_testing}" ]]; then
    BUILD_NOTIFY_LINES+=("Firebase App Distribution (testers / install): ${fad_testing}")
  elif [[ -n "${fad_console}" ]]; then
    BUILD_NOTIFY_LINES+=("Firebase App Distribution (console): ${fad_console}")
  elif [[ -n "${play_internal_sharing}" ]]; then
    BUILD_NOTIFY_LINES+=("Internal App Sharing: ${play_internal_sharing}")
    BUILD_NOTIFY_LINES+=("(Recipients must be allowed for Internal App Sharing in Play Console.)")
  else
    if [[ -n "${artifact_url}" ]]; then
      BUILD_NOTIFY_LINES+=("Download artifact (ZIP with ${bundle_kind}): ${artifact_url}")
    else
      BUILD_NOTIFY_LINES+=("${bundle_kind}: open the workflow run → Artifacts → ${artifact:-signed build ZIP} (contains the ${bundle_kind}).")
    fi
    BUILD_NOTIFY_LINES+=("(GitHub login and repo access required.)")
  fi
}

url="${SLACK_TRIGGER_WEBHOOK_URL:-}"
if [[ -z "${url}" ]]; then
  echo "::notice::Skipping Slack: SLACK_TRIGGER_WEBHOOK_URL secret is not set."
  exit 0
fi

BUILD_NOTIFY_LINES=()
append_metadata_lines
metadata_line_count=${#BUILD_NOTIFY_LINES[@]}

append_distribution_lines

notes="${BUILD_RELEASE_NOTES:-}"
if [[ -n "${notes}" ]]; then
  BUILD_NOTIFY_LINES+=("Notes: ${notes}")
fi

message=""
idx=0
for line in "${BUILD_NOTIFY_LINES[@]}"; do
  if [[ "${metadata_line_count}" -gt 0 && "${idx}" -eq "${metadata_line_count}" ]]; then
    message+=$'\n'
  fi
  message+="${line}"$'\n'
  idx=$((idx + 1))
done

payload="$(jq -n --arg message "${message}" '{"message": $message}')"
http_code="$(
  curl -sS -o /tmp/slack_webhook_response.txt -w '%{http_code}' \
    -X POST \
    -H 'Content-type: application/json' \
    --data-binary "${payload}" \
    "${url}"
)"

if [[ "${http_code}" != "200" && "${http_code}" != "201" ]]; then
  echo "::error::Slack webhook returned HTTP ${http_code}"
  cat /tmp/slack_webhook_response.txt >&2 || true
  exit 1
fi

echo "Slack notification sent (HTTP ${http_code})."
