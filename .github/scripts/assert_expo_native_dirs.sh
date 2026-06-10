#!/usr/bin/env bash
# Usage: assert_expo_native_dirs.sh <build_system>
# If build_system is "expo", require committed android/ and ios/ trees (post prebuild).
# For "bare" or anything else, no-op success (so this job can be a required needs for all native builds).
set -euo pipefail

BUILD_SYSTEM="${1:-}"

if [ "$BUILD_SYSTEM" != "expo" ]; then
  echo "build_system is '${BUILD_SYSTEM}' (not expo); skipping native directory check."
  exit 0
fi

fail() {
  echo "::error::$1"
}

missing=0

if [ ! -f android/app/build.gradle ]; then
  fail "Expo CI requires committed native projects. Missing android/app/build.gradle. Run: npx expo prebuild --clean (with the correct APP_ENV for your flavor), then commit the android/ and ios/ directories and push again."
  missing=1
fi

if [ ! -f ios/Podfile ]; then
  fail "Expo CI requires committed native projects. Missing ios/Podfile. Run: npx expo prebuild --clean (with the correct APP_ENV for your flavor), then commit the android/ and ios/ directories and push again."
  missing=1
fi

shopt -s nullglob
xc=(ios/*.xcodeproj)
if [ "${#xc[@]}" -eq 0 ]; then
  fail "Expo CI requires an Xcode project under ios/. Run: npx expo prebuild --clean, then commit ios/."
  missing=1
fi

if [ "$missing" -ne 0 ]; then
  exit 1
fi

echo "Expo native directories (android/, ios/) present."
