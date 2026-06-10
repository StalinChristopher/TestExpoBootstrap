# GitHub Actions secrets checklist

Add these in **GitHub → Settings → Secrets and variables → Actions** (repository or environment).
Values are never committed here — only names and hints.

| Secret | Optional | Used in workflows | Where to get it |
| --- | --- | --- | --- |
| `APP_COMPANY_NAME` | yes | rn-job-ios-internal-release.yml | See the referenced workflow job and your store / Firebase / Play consoles. |
| `APP_STORE_CONNECT_API_KEY` | no | rn-job-ios-internal-release.yml | App Store Connect API key — private key (.p8) contents. |
| `APP_STORE_CONNECT_ISSUER_ID` | no | rn-job-ios-internal-release.yml | App Store Connect API key — Issuer ID. |
| `APP_STORE_CONNECT_KEY_ID` | no | rn-job-ios-internal-release.yml | App Store Connect API key — Key ID. |
| `DIST_CERTIFICATE_BASE64` | no | rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml | Distribution signing certificate (.p12) base64. |
| `DIST_CERTIFICATE_DEV_BASE64` | yes | rn-job-ios-firebase-release.yml | Development / ad-hoc certificate base64 (iOS Firebase dev builds). |
| `DIST_CERTIFICATE_DEV_PASSWORD` | yes | rn-job-ios-firebase-release.yml | Password for dev signing .p12. |
| `DIST_CERTIFICATE_PASSWORD` | no | rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml | Password for the distribution .p12. |
| `DIST_PROFILE_BASE64` | no | rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml | Provisioning profile (.mobileprovision) base64 for distribution. |
| `DIST_PROFILE_DEV_BASE64` | yes | rn-job-ios-firebase-release.yml | Development provisioning profile base64. |
| `FIREBASE_ANDROID_APP_ID` | no | rn-job-android-firebase-release.yml | Firebase Console → Project settings → Your apps → Android (prod / dist applicationId). |
| `FIREBASE_ANDROID_DEV_APP_ID` | no | rn-job-android-firebase-release.yml | Firebase Android app for the dev applicationId. |
| `FIREBASE_IOS_APP_ID` | no | rn-job-ios-firebase-release.yml | Firebase iOS app ID for distribution / prod bundle. |
| `FIREBASE_IOS_DEV_APP_ID` | no | rn-job-ios-firebase-release.yml | Firebase iOS app ID for dev bundle. |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | no | rn-job-android-firebase-release.yml, rn-job-ios-firebase-release.yml | Firebase service account JSON with App Distribution Admin (or broader) for CI. |
| `GOOGLE_SERVICES_JSON` | yes | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml, rn-job-android-perf.yml, rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml, rn-job-ios-performance.yml, rn-performance-baseline.yml | Full google-services.json from Firebase Console (Android; may include all flavor package_name clients). |
| `GOOGLE_SERVICE_INFO_PLIST` | yes | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml, rn-job-android-perf.yml, rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml, rn-job-ios-performance.yml, rn-performance-baseline.yml | Optional fallback iOS plist when only one Firebase iOS app is used in CI. |
| `GOOGLE_SERVICE_INFO_PLIST_DEV` | yes | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml, rn-job-android-perf.yml, rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml, rn-job-ios-performance.yml, rn-performance-baseline.yml | GoogleService-Info.plist for dev/QA bundle ID — restored in CI before iOS dev builds. |
| `GOOGLE_SERVICE_INFO_PLIST_DIST` | yes | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml, rn-job-android-perf.yml, rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml, rn-job-ios-performance.yml, rn-performance-baseline.yml | GoogleService-Info.plist for production bundle ID — restored in CI before iOS dist/TestFlight builds. |
| `IOS_CODESIGN_IDENTITY` | yes | rn-job-ios-firebase-release.yml, rn-job-ios-internal-release.yml | Codesign identity string shown by `security find-identity -v -p codesigning` on the runner keychain setup. |
| `PLAY_SERVICE_ACCOUNT_JSON` | no | rn-job-android-internal-release.yml | Google Play service account JSON (Android internal release → Play Internal App Sharing). |
| `RELEASE_KEYSTORE_BASE64` | no | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml | Base64-encoded Android release keystore file. |
| `RELEASE_KEYSTORE_PASSWORD` | no | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml | Android keystore store password. |
| `RELEASE_KEY_ALIAS` | no | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml | Android keystore key alias. |
| `RELEASE_KEY_PASSWORD` | no | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml | Android keystore key password. |
| `SLACK_TRIGGER_WEBHOOK_URL` | yes | rn-job-android-firebase-release.yml, rn-job-android-internal-release.yml, rn-job-ios-firebase-release.yml | Optional Slack Workflow Builder webhook trigger URL; workflow Text variable must be named message (see notify_slack_workflow_webhook.sh). |
| `SNYK_TOKEN` | yes | rn-job-security.yml | Optional — https://snyk.io ; if unset, Snyk step is skipped. |

_Generated by `.github/scripts/list_workflow_secrets.py` — re-run after you add or change workflows._
