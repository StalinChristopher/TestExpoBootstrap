#!/usr/bin/env bash
# Restore google-services.json and GoogleService-Info.plist from GitHub Secrets for CI builds.
# See docs/RN_WORKFLOW_REUSE.md and .github/firebase-client-paths.example.json
set -euo pipefail

FIREBASE_FLAVOR="${FIREBASE_FLAVOR:-dev}"
PATHS_FILE="${FIREBASE_CLIENT_PATHS_FILE:-.github/firebase-client-paths.json}"

firebase_required() {
  if [ -f package.json ] && grep -q '@react-native-firebase/app' package.json 2>/dev/null; then
    return 0
  fi
  if [ -f android/app/build.gradle ] && grep -q 'com.google.gms.google-services' android/app/build.gradle 2>/dev/null; then
    return 0
  fi
  return 1
}

if ! firebase_required; then
  echo "::notice::Firebase client config not required (no @react-native-firebase/app or google-services plugin) — skipping restore"
  exit 0
fi

normalize_flavor() {
  local f
  f="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$f" in
    dev|development) echo dev ;;
    dist|prod|production) echo dist ;;
    *) echo "$f" ;;
  esac
}

FIREBASE_FLAVOR="$(normalize_flavor "$FIREBASE_FLAVOR")"

write_file_from_secret() {
  local dest="$1"
  local content="$2"
  local label="$3"
  if [ -z "$content" ]; then
    echo "::error::Missing secret content for ${label} (destination: ${dest})"
    echo "::error::Add ${label} in GitHub → Settings → Secrets and variables → Actions (see GITHUB_SECRETS_CHECKLIST.md)"
    return 1
  fi
  mkdir -p "$(dirname "$dest")"
  printf '%s' "$content" > "$dest"
  chmod 600 "$dest"
  echo "Restored ${label} → ${dest}"
}

resolve_paths() {
  python3 - "$PATHS_FILE" "$FIREBASE_FLAVOR" <<'PY'
import json
import os
import sys
from pathlib import Path

paths_file = sys.argv[1]
flavor = sys.argv[2]

def load_app_json_paths():
    android_paths = []
    ios_paths = {"dev": [], "dist": []}
    for name in ("app.json", "app.config.json"):
        p = Path(name)
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        expo = data.get("expo") or data
        a = expo.get("android", {}).get("googleServicesFile")
        i = expo.get("ios", {}).get("googleServicesFile")
        if a:
            android_paths.append(a.lstrip("./"))
        if i:
            plist = i.lstrip("./")
            ios_paths["dev"].append(plist)
            ios_paths["dist"].append(plist)
        break
    return android_paths, ios_paths

def load_paths_file():
    p = Path(paths_file)
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    android = list(data.get("android") or [])
    ios_raw = data.get("ios") or {}
    if isinstance(ios_raw, list):
        ios = {"dev": list(ios_raw), "dist": list(ios_raw)}
    else:
        ios = {
            "dev": list(ios_raw.get("dev") or []),
            "dist": list(ios_raw.get("dist") or []),
        }
    return android, ios

android_paths: list[str] = []
ios_paths = {"dev": [], "dist": []}

from_file = load_paths_file()
if from_file:
    android_paths, ios_paths = from_file
else:
    a, i = load_app_json_paths()
    android_paths.extend(a)
    ios_paths["dev"].extend(i["dev"])
    ios_paths["dist"].extend(i["dist"])

# Standard Android module path when native tree exists
if Path("android/app").is_dir() and "android/app/google-services.json" not in android_paths:
    android_paths.append("android/app/google-services.json")

def dedupe(seq):
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

android_paths = dedupe(android_paths)
ios_paths["dev"] = dedupe(ios_paths["dev"])
ios_paths["dist"] = dedupe(ios_paths["dist"])

# If only one flavor list is populated, mirror to the other
if ios_paths["dev"] and not ios_paths["dist"]:
    ios_paths["dist"] = list(ios_paths["dev"])
elif ios_paths["dist"] and not ios_paths["dev"]:
    ios_paths["dev"] = list(ios_paths["dist"])

print(json.dumps({"android": android_paths, "ios": ios_paths}))
PY
}

PATHS_JSON="$(resolve_paths)"
ANDROID_PATHS="$(echo "$PATHS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(d['android']))")"
IOS_PATHS="$(echo "$PATHS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(d['ios'].get(sys.argv[1],[])))" "$FIREBASE_FLAVOR")"

if [ -z "$ANDROID_PATHS" ] && [ -z "$IOS_PATHS" ]; then
  echo "::error::No Firebase client config paths resolved. Add .github/firebase-client-paths.json or expo.googleServicesFile in app.json"
  exit 1
fi

# Android
if [ -n "$ANDROID_PATHS" ]; then
  if [ -z "${GOOGLE_SERVICES_JSON:-}" ]; then
    echo "::error::Firebase Android build requires GOOGLE_SERVICES_JSON secret"
    exit 1
  fi
  while IFS= read -r dest; do
    [ -n "$dest" ] || continue
    write_file_from_secret "$dest" "$GOOGLE_SERVICES_JSON" "GOOGLE_SERVICES_JSON"
  done <<< "$ANDROID_PATHS"
fi

# iOS plist for flavor
if [ -n "$IOS_PATHS" ]; then
  PLIST_CONTENT=""
  PLIST_SECRET=""
  if [ "$FIREBASE_FLAVOR" = "dev" ]; then
    if [ -n "${GOOGLE_SERVICE_INFO_PLIST_DEV:-}" ]; then
      PLIST_CONTENT="$GOOGLE_SERVICE_INFO_PLIST_DEV"
      PLIST_SECRET="GOOGLE_SERVICE_INFO_PLIST_DEV"
    elif [ -n "${GOOGLE_SERVICE_INFO_PLIST:-}" ]; then
      PLIST_CONTENT="$GOOGLE_SERVICE_INFO_PLIST"
      PLIST_SECRET="GOOGLE_SERVICE_INFO_PLIST"
    fi
  else
    if [ -n "${GOOGLE_SERVICE_INFO_PLIST_DIST:-}" ]; then
      PLIST_CONTENT="$GOOGLE_SERVICE_INFO_PLIST_DIST"
      PLIST_SECRET="GOOGLE_SERVICE_INFO_PLIST_DIST"
    elif [ -n "${GOOGLE_SERVICE_INFO_PLIST:-}" ]; then
      PLIST_CONTENT="$GOOGLE_SERVICE_INFO_PLIST"
      PLIST_SECRET="GOOGLE_SERVICE_INFO_PLIST"
    fi
  fi
  if [ -z "$PLIST_CONTENT" ]; then
    FLAVOR_UPPER="$(printf '%s' "$FIREBASE_FLAVOR" | tr '[:lower:]' '[:upper:]')"
    echo "::error::Firebase iOS build (flavor=${FIREBASE_FLAVOR}) requires GOOGLE_SERVICE_INFO_PLIST_${FLAVOR_UPPER} or GOOGLE_SERVICE_INFO_PLIST"
    exit 1
  fi
  while IFS= read -r dest; do
    [ -n "$dest" ] || continue
    write_file_from_secret "$dest" "$PLIST_CONTENT" "$PLIST_SECRET"
  done <<< "$IOS_PATHS"
fi

echo "Firebase client config restore complete (flavor=${FIREBASE_FLAVOR})"
