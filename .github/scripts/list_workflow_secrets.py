#!/usr/bin/env python3
"""
Scan .github/workflows for GitHub Actions secret names and emit a checklist
for repository Settings → Secrets and variables → Actions.

Usage (from repository root):
  python3 .github/scripts/list_workflow_secrets.py
  python3 .github/scripts/list_workflow_secrets.py --write GITHUB_SECRETS_CHECKLIST.md
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")

# Secrets that are explicitly optional in workflow_call or commonly skipped at runtime.
OPTIONAL_NAMES = frozenset({"SNYK_TOKEN", "SLACK_TRIGGER_WEBHOOK_URL"})

HINTS: dict[str, str] = {
    "EXPO_TOKEN": "Expo account → https://expo.dev/accounts/[account]/settings/access-tokens (EAS / Expo workflows).",
    "SNYK_TOKEN": "Optional — https://snyk.io ; if unset, Snyk step is skipped.",
    "RELEASE_KEYSTORE_BASE64": "Base64-encoded Android release keystore file.",
    "RELEASE_KEYSTORE_PASSWORD": "Android keystore store password.",
    "RELEASE_KEY_ALIAS": "Android keystore key alias.",
    "RELEASE_KEY_PASSWORD": "Android keystore key password.",
    "FIREBASE_ANDROID_APP_ID": "Firebase Console → Project settings → Your apps → Android (prod / dist applicationId).",
    "FIREBASE_ANDROID_DEV_APP_ID": "Firebase Android app for the dev applicationId.",
    "FIREBASE_IOS_APP_ID": "Firebase iOS app ID for distribution / prod bundle.",
    "FIREBASE_IOS_DEV_APP_ID": "Firebase iOS app ID for dev bundle.",
    "FIREBASE_SERVICE_ACCOUNT_JSON": "Firebase service account JSON with App Distribution Admin (or broader) for CI.",
    "GOOGLE_SERVICES_JSON": "Full google-services.json from Firebase Console (Android; may include all flavor package_name clients).",
    "GOOGLE_SERVICE_INFO_PLIST_DEV": "GoogleService-Info.plist for dev/QA bundle ID — restored in CI before iOS dev builds.",
    "GOOGLE_SERVICE_INFO_PLIST_DIST": "GoogleService-Info.plist for production bundle ID — restored in CI before iOS dist/TestFlight builds.",
    "GOOGLE_SERVICE_INFO_PLIST": "Optional fallback iOS plist when only one Firebase iOS app is used in CI.",
    "PLAY_SERVICE_ACCOUNT_JSON": "Google Play service account JSON (Android internal release → Play Internal App Sharing).",
    "DIST_CERTIFICATE_BASE64": "Distribution signing certificate (.p12) base64.",
    "DIST_CERTIFICATE_PASSWORD": "Password for the distribution .p12.",
    "DIST_PROFILE_BASE64": "Provisioning profile (.mobileprovision) base64 for distribution.",
    "DIST_CERTIFICATE_DEV_BASE64": "Development / ad-hoc certificate base64 (iOS Firebase dev builds).",
    "DIST_CERTIFICATE_DEV_PASSWORD": "Password for dev signing .p12.",
    "DIST_PROFILE_DEV_BASE64": "Development provisioning profile base64.",
    "APP_STORE_CONNECT_KEY_ID": "App Store Connect API key — Key ID.",
    "APP_STORE_CONNECT_ISSUER_ID": "App Store Connect API key — Issuer ID.",
    "APP_STORE_CONNECT_API_KEY": "App Store Connect API key — private key (.p8) contents.",
    "IOS_CODESIGN_IDENTITY": "Codesign identity string shown by `security find-identity -v -p codesigning` on the runner keychain setup.",
    "SLACK_TRIGGER_WEBHOOK_URL": "Optional Slack Workflow Builder webhook trigger URL; workflow Text variable must be named message (see notify_slack_workflow_webhook.sh).",
}


def collect_secret_refs(workflow_text: str) -> set[str]:
    return set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow_text))


def collect_workflow_call_optional(workflow_text: str) -> set[str]:
    """Names declared under workflow_call.secrets with required: false."""
    optional: set[str] = set()
    # Match secret key at typical indent followed by required: false
    for m in re.finditer(
        r"(?m)^\s{2,8}([A-Z0-9_]+):\s*$\n\s+required:\s*false\s*$",
        workflow_text,
    ):
        optional.add(m.group(1))
    return optional


def main() -> int:
    parser = argparse.ArgumentParser(description="List GitHub Actions secret names used by workflows.")
    parser.add_argument(
        "--write",
        metavar="FILE",
        help="Write markdown checklist to FILE (default: stdout only).",
    )
    parser.add_argument(
        "--workflows-dir",
        type=Path,
        default=WORKFLOW_DIR,
        help="Directory containing workflow YAML (default: .github/workflows).",
    )
    args = parser.parse_args()

    if not args.workflows_dir.is_dir():
        print(f"error: not a directory: {args.workflows_dir}", file=sys.stderr)
        return 1

    per_secret_files: dict[str, set[str]] = defaultdict(set)
    declared_optional: set[str] = set()

    for path in sorted(args.workflows_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        declared_optional |= collect_workflow_call_optional(text)
        for name in collect_secret_refs(text):
            per_secret_files[name].add(path.name)

    if not per_secret_files:
        print("error: no secrets.* references found", file=sys.stderr)
        return 1

    lines: list[str] = [
        "# GitHub Actions secrets checklist",
        "",
        "Add these in **GitHub → Settings → Secrets and variables → Actions** (repository or environment).",
        "Values are never committed here — only names and hints.",
        "",
        "| Secret | Optional | Used in workflows | Where to get it |",
        "| --- | --- | --- | --- |",
    ]

    for name in sorted(per_secret_files):
        optional = name in OPTIONAL_NAMES or name in declared_optional
        opt_cell = "yes" if optional else "no"
        files_cell = ", ".join(sorted(per_secret_files[name]))
        hint = HINTS.get(name, "See the referenced workflow job and your store / Firebase / Play consoles.")
        lines.append(f"| `{name}` | {opt_cell} | {files_cell} | {hint} |")

    lines.append("")
    lines.append(
        "_Generated by `.github/scripts/list_workflow_secrets.py` — re-run after you add or change workflows._"
    )
    lines.append("")

    body = "\n".join(lines)
    if args.write:
        out = Path(args.write)
        out.write_text(body, encoding="utf-8")
        print(f"Wrote {out.resolve()}")
    else:
        print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
