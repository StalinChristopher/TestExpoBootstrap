#!/usr/bin/env bash
# Runs iOS UI performance tests on a simulator (GitHub Actions macOS runners or self-hosted).
# Exit code from xcodebuild is preserved (pipefail + PIPESTATUS).
#
# Do not use CODE_SIGNING_ALLOWED=NO — it breaks embedding/running UI test bundles on many Xcode versions.
set -euo pipefail

# Ensure timeout command is available (macOS uses gtimeout from coreutils)
if ! command -v timeout &> /dev/null; then
  if command -v gtimeout &> /dev/null; then
    timeout() { gtimeout "$@"; }
  else
    echo "::warning::timeout command not available, timeouts will not be enforced"
    timeout() { shift; "$@"; }
  fi
fi

ROOT="${GITHUB_WORKSPACE:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
BUILD_DIR="${ROOT}/build"
mkdir -p "${BUILD_DIR}"

if [[ -x "${ROOT}/.github/scripts/restore_ci_env_files.sh" ]]; then
  bash "${ROOT}/.github/scripts/restore_ci_env_files.sh"
fi

IOS_WORKSPACE="${IOS_WORKSPACE:-ios/TestExpoBootstrapDev.xcworkspace}"
IOS_SCHEME="${IOS_SCHEME:-Dev}"
IOS_BUILD_CONFIGURATION="${IOS_BUILD_CONFIGURATION:-Debug-Dev}"
IOS_PERFORMANCE_TEST_CLASS="${IOS_PERFORMANCE_TEST_CLASS:-TemplatePipelineReactNativeUITests/AppPerformanceTests}"

# full = launch + CPU/memory (PR table like PerformanceTest_iOS). launch = fast local smoke.
PERF_METRICS_MODE="${PERF_METRICS_MODE:-full}"
if [[ -n "${IOS_PERFORMANCE_ONLY_TEST:-}" ]]; then
  :
elif [[ "${PERF_METRICS_MODE}" == "launch" ]]; then
  IOS_PERFORMANCE_ONLY_TEST="${IOS_PERFORMANCE_TEST_CLASS}/testLaunchPerformance"
else
  IOS_PERFORMANCE_ONLY_TEST="${IOS_PERFORMANCE_TEST_CLASS}"
fi

if [[ ! -d "${ROOT}/${IOS_WORKSPACE}" ]]; then
  echo "::error::Missing workspace: ${ROOT}/${IOS_WORKSPACE}"
  exit 2
fi

IOS_PLIST="${ROOT}/ios/TestExpoBootstrapDev/GoogleService-Info.plist"
if [[ ! -f "${IOS_PLIST}" ]]; then
  if [[ -f "${ROOT}/GoogleService-Info.plist.example" ]]; then
    cp "${ROOT}/GoogleService-Info.plist.example" "${IOS_PLIST}"
    echo "GoogleService-Info.plist missing — copied .example placeholder (set real plist via CI secrets for production)."
  else
    echo "::warning::GoogleService-Info.plist missing and no .example found — Crashlytics build phase may fail."
  fi
fi
# Extract GOOGLE_APP_ID from the plist so the Crashlytics run-script can read it
# from the xcodebuild environment even when the plist is not yet embedded in the app bundle.
GOOGLE_APP_ID_VALUE=""
if [[ -f "${IOS_PLIST}" ]]; then
  GOOGLE_APP_ID_VALUE=$(python3 -c "
import plistlib, sys
try:
  with open('${IOS_PLIST}', 'rb') as f:
    d = plistlib.load(f)
  print(d.get('GOOGLE_APP_ID', ''))
except Exception:
  print('')
" 2>/dev/null || true)
fi

DESTINATION="${SIMULATOR_DESTINATION:-}"
if [[ -z "${DESTINATION}" || "${DESTINATION}" = "auto" ]]; then
  DESTINATION="$(python3 "${ROOT}/.github/scripts/ios_first_iphone_sim_udid.py")"
fi
echo "Destination: ${DESTINATION}"
echo "Available simulators:"
xcrun simctl list devices available | grep -E "iPhone|iPad" | head -10

if [[ "${DESTINATION}" == *"id="* ]]; then
  UDID="${DESTINATION#*id=}"
  UDID="${UDID%%[, ]*}"
elif [[ "${DESTINATION}" == *"platform=iOS Simulator"* ]]; then
  UDID="$(python3 "${ROOT}/.github/scripts/ios_first_iphone_sim_udid.py" --udid)"
fi
if [[ -n "${UDID:-}" ]]; then
  echo "Preparing simulator ${UDID}..."
  # Shutdown first so we always start from a clean state.
  # Leftover state from a previous run or a crashed simulator causes
  # bootstatus to return Status=4294967295 (-1) mid-wait.
  xcrun simctl shutdown "${UDID}" 2>/dev/null || true
  sleep 2
  xcrun simctl boot "${UDID}" 2>/dev/null || true

  # Wait up to 120 s for the simulator to reach Booted.
  # On failure we warn and let xcodebuild attempt its own boot rather than
  # aborting the job — a hard exit here is worse than handing off to xcodebuild.
  echo "Waiting for simulator to reach Booted state..."
  if ! timeout 120 xcrun simctl bootstatus "${UDID}" -b 2>&1; then
    echo "::warning::simctl bootstatus reported a boot issue (Status=4294967295 or timeout) — xcodebuild will attempt to boot the simulator"
    sleep 5
  fi

  # Confirm final state for diagnostics.
  SIM_STATE=$(xcrun simctl list devices | grep "${UDID}" | grep -o "Booted\|Shutdown\|Booting" || echo "Unknown")
  echo "Simulator state after boot attempt: ${SIM_STATE}"
fi

cd "${ROOT}"

rm -rf "${BUILD_DIR}/TestResults.xcresult"

# PREBUILT_DERIVED_DATA: when set, skip Phase 1 (build-for-testing) and use the
# pre-built test products downloaded from the ios-dev job artifact.
# The derived data must have been built on a runner with the same GITHUB_WORKSPACE
# path (guaranteed for GitHub-hosted macos-* runners — all use the same path pattern).
DERIVED_DATA_PATH="${PREBUILT_DERIVED_DATA:-${BUILD_DIR}/DerivedData}"

# Use a plain string, not an array: bash 3.2 (macOS default) treats
# "${empty_array[@]}" as an unbound variable when set -u is active.
RETRY_FLAG=""
if [[ "${PERF_METRICS_MODE}" == "launch" ]]; then
  RETRY_FLAG="-retry-tests-on-failure"
fi

if [[ -n "${PREBUILT_DERIVED_DATA:-}" ]]; then
  # ── Pre-built mode: skip Phase 1 ─────────────────────────────────────────
  echo "PREBUILT_DERIVED_DATA=${PREBUILT_DERIVED_DATA} — skipping build-for-testing phase."
  echo "Using pre-built test products from: ${DERIVED_DATA_PATH}/Build/Products"
  if [[ ! -d "${DERIVED_DATA_PATH}/Build/Products" ]]; then
    echo "::error::Pre-built test products not found at ${DERIVED_DATA_PATH}/Build/Products"
    exit 2
  fi
  # Verify JS bundle was embedded in the pre-built app
  PRODUCTS_DIR="${DERIVED_DATA_PATH}/Build/Products/${IOS_BUILD_CONFIGURATION}-iphonesimulator"
  BUILT_APP="$(find "${PRODUCTS_DIR}" -maxdepth 1 -name "*.app" ! -name "*UITests*" 2>/dev/null | head -1 || true)"
  if [[ -n "${BUILT_APP}" && -f "${BUILT_APP}/main.jsbundle" ]]; then
    echo "✓ main.jsbundle confirmed in pre-built app: ${BUILT_APP}"
  else
    echo "::warning::main.jsbundle NOT found in ${BUILT_APP:-${PRODUCTS_DIR}} — testTypicalSessionCPUAndMemory will be skipped by XCTSkip"
  fi
else
  # ── Phase 1: build-for-testing ─────────────────────────────────────────────
  # Separating build from test gives a clear build-error signal and lets us
  # verify that main.jsbundle was embedded (FORCE_BUNDLING=1) before tests run.
  echo "Building + running: ${IOS_PERFORMANCE_ONLY_TEST} (PERF_METRICS_MODE=${PERF_METRICS_MODE}, configuration=${IOS_BUILD_CONFIGURATION})"

  # Pre-flight check: ensure xcodebuild can see the workspace
  if ! xcodebuild -list -workspace "${IOS_WORKSPACE}" &>/dev/null; then
    echo "::error::xcodebuild cannot access workspace ${IOS_WORKSPACE}"
    exit 2
  fi
  echo "Workspace validated: ${IOS_WORKSPACE}"

  # Clean derived data before building to avoid stale module cache and pre-compiled
  # pod artifacts from a mismatched Xcode version (equivalent to local 'delete Derived
  # Data' + 'pod update' fix for exit code 65 compilation errors).
  echo "Cleaning derived data at ${DERIVED_DATA_PATH} before build..."
  rm -rf "${DERIVED_DATA_PATH}"

  # Always provide a GOOGLE_APP_ID so the FirebaseCrashlytics run-script does not
  # fail when the plist contains a placeholder value (primary cause of exit code 65
  # on first-time CI runs or simulator-only builds).
  # The real value from the plist is preferred; fall back to a placeholder whose
  # format satisfies the Crashlytics format check without triggering a network upload.
  if [[ -z "${GOOGLE_APP_ID_VALUE}" ]]; then
    GOOGLE_APP_ID_VALUE="1:000000000000:ios:0000000000000000000000"
    echo "::notice::GOOGLE_APP_ID not found in plist — using CI placeholder so Crashlytics build phase does not fail."
  fi

  echo "Starting build-for-testing phase (timeout: 20 minutes)..."
  set +e
  timeout 1200 xcodebuild build-for-testing \
    -workspace "${IOS_WORKSPACE}" \
    -scheme "${IOS_SCHEME}" \
    -configuration "${IOS_BUILD_CONFIGURATION}" \
    -sdk iphonesimulator \
    -destination "${DESTINATION}" \
    -derivedDataPath "${DERIVED_DATA_PATH}" \
    -only-testing:"${IOS_PERFORMANCE_ONLY_TEST}" \
    -skip-testing:TemplatePipelineReactNativeTests \
    CODE_SIGN_IDENTITY=- \
    CODE_SIGNING_REQUIRED=NO \
    CODE_SIGNING_ALLOWED=YES \
    FORCE_BUNDLING=1 \
    EXCLUDED_ARCHS= \
    GCC_TREAT_WARNINGS_AS_ERRORS=NO \
    SWIFT_TREAT_WARNINGS_AS_ERRORS=NO \
    DEBUG_INFORMATION_FORMAT=dwarf \
    COMPILER_INDEX_STORE_ENABLE=NO \
    CLANG_ENABLE_MODULE_DEBUGGING=NO \
    GOOGLE_APP_ID="${GOOGLE_APP_ID_VALUE}" \
    2>&1 | tee "${BUILD_DIR}/xcodebuild-test.log"
  BUILD_EXIT="${PIPESTATUS[0]}"
  set -e

  if [[ "${BUILD_EXIT}" -eq 124 ]]; then
    echo "::error::xcodebuild build-for-testing timed out after 20 minutes"
    tail -n 100 "${BUILD_DIR}/xcodebuild-test.log" || true
    exit "${BUILD_EXIT}"
  elif [[ "${BUILD_EXIT}" -ne 0 ]]; then
    echo "::error::xcodebuild build-for-testing failed with exit code ${BUILD_EXIT}"
    echo "--- Last 100 lines of build log ---"
    tail -n 100 "${BUILD_DIR}/xcodebuild-test.log" || true
    exit "${BUILD_EXIT}"
  fi
  echo "Build-for-testing completed successfully"

  # Verify JS bundle was embedded
  PRODUCTS_DIR="${DERIVED_DATA_PATH}/Build/Products/${IOS_BUILD_CONFIGURATION}-iphonesimulator"
  BUILT_APP="$(find "${PRODUCTS_DIR}" -maxdepth 1 -name "*.app" ! -name "*UITests*" 2>/dev/null | head -1 || true)"
  if [[ -n "${BUILT_APP}" && -f "${BUILT_APP}/main.jsbundle" ]]; then
    echo "✓ main.jsbundle found in built app: ${BUILT_APP}"
  else
    echo "::warning::main.jsbundle NOT found in ${BUILT_APP:-${PRODUCTS_DIR}} — testTypicalSessionCPUAndMemory will be skipped by XCTSkip"
  fi
fi

# ── Phase 2: test-without-building ─────────────────────────────────────────
echo "Starting test-without-building phase (timeout: 20 minutes)..."
echo "Running test: ${IOS_PERFORMANCE_ONLY_TEST}"
set +e
timeout 1200 xcodebuild test-without-building \
  -workspace "${IOS_WORKSPACE}" \
  -scheme "${IOS_SCHEME}" \
  -configuration "${IOS_BUILD_CONFIGURATION}" \
  -sdk iphonesimulator \
  -destination "${DESTINATION}" \
  -derivedDataPath "${DERIVED_DATA_PATH}" \
  -only-testing:"${IOS_PERFORMANCE_ONLY_TEST}" \
  -skip-testing:TemplatePipelineReactNativeTests \
  -resultBundlePath "${BUILD_DIR}/TestResults.xcresult" \
  -parallel-testing-enabled NO \
  -maximum-concurrent-test-simulator-destinations 1 \
  ${RETRY_FLAG:+"${RETRY_FLAG}"} \
  ${GOOGLE_APP_ID_VALUE:+GOOGLE_APP_ID="${GOOGLE_APP_ID_VALUE}"} \
  2>&1 | tee -a "${BUILD_DIR}/xcodebuild-test.log"
XCODE_EXIT="${PIPESTATUS[0]}"
set -e

if [[ "${XCODE_EXIT}" -eq 124 ]]; then
  echo "::error::xcodebuild test-without-building timed out after 20 minutes"
  echo "Last 100 lines of xcodebuild log:"
  tail -n 100 "${BUILD_DIR}/xcodebuild-test.log" || true
  echo ""
  echo "Checking simulator state..."
  xcrun simctl list devices | grep -A1 "${UDID:-}" || true
  exit "${XCODE_EXIT}"
elif [[ "${XCODE_EXIT}" -ne 0 ]]; then
  echo "::error::xcodebuild test-without-building failed with exit code ${XCODE_EXIT}"
  tail -n 80 "${BUILD_DIR}/xcodebuild-test.log" || true
  exit "${XCODE_EXIT}"
fi
echo "Test execution completed successfully"
