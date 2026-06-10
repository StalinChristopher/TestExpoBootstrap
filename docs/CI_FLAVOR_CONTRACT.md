# CI flavor contract (CT template ↔ pipeline kit)

**Source of truth:** [ct-react-native-template](https://github.com/codeandtheory/ct-react-native-template) `templates/CliTemplate/ios` and `android/app/build.gradle`.

When CT flavor layout changes, update **this repo’s** `ios/` sample, workflow defaults, and `bootstrap_rn_workflow_ids.py` in the same change.

**Kit sample placeholders:** `com.codeandtheory.templatepipelinetest` (prod), `.dev`, `.qa` — bootstrap replaces these in workflows when applied to another app.

## iOS

| Concern | Dev | QA | Prod (dist / CI) |
|---------|-----|-----|------------------|
| Scheme | `Dev` | `QA` | `Prod` |
| Debug config | `Debug-Dev` | `Debug-QA` | `Debug-Prod` |
| Release / archive config | `Release-Dev` | `Release-QA` | `Release-Prod` |
| xcconfig | `ios/xcconfig/Dev.*` | `ios/xcconfig/QA.*` | `ios/xcconfig/Prod.*` |
| Bundle ID | `{packageId}.dev` | `{packageId}.qa` | `{packageId}` (base, **no `.dist`**) |

### CI mapping

| Job | Scheme | `IOS_BUILD_CONFIGURATION` | Bundle ID |
|-----|--------|---------------------------|-------------|
| ios-dev / Firebase dev | `Dev` | `Debug-Dev` | `*.dev` |
| ios-dist / Firebase dist / TestFlight | `Prod` | `Release-Prod` | base prod |

Legacy `{AppName}.xcscheme` (plain `Debug`/`Release`) is for local use only — **workflows must not use it**.

## Android

| Flavor | `applicationId` |
|--------|-----------------|
| `dev` | `{namespace}.dev` |
| `qa` | `{namespace}.qa` |
| `prod` | base `applicationId` (no suffix) |

CI dist: `assembleProdRelease`. CI dev: `assembleDevRelease`.

## Bootstrap

After applying this kit, run from the app repo root:

```bash
python3 .github/scripts/bootstrap_rn_workflow_ids.py
```

Bootstrap renames sample placeholder IDs/schemes to match the app’s `ios/xcconfig` and `Dev`/`Prod` schemes, and sets **`android-perf`** in `rn.yml` to the dev flavor’s **`applicationId`** plus **`{applicationId}/{namespace}.MainActivity`** from `android/app/build.gradle`.

**Bootstrap substitution rules** (`bootstrap_rn_workflow_ids.py`):

- Never substring-replace bare `Dev` or `Prod` across workflow YAML — scheme names like `ExpoWorkflowTestDev` would be corrupted (e.g. `assembleExpoWorkflowTestExpoWorkflowTestDevRelease`).
- iOS scheme substitution is **regex-scoped** to `ios_scheme:` / `IOS_SCHEME:` fields and `ios_scheme` workflow input defaults only.
- Android Gradle task names (`assembleDevRelease`, `assembleProdRelease`) come from **`productFlavors`** in `android/app/build.gradle`, **not** from iOS scheme names.
- iOS build configurations (`Debug-Dev`, `Release-Prod`) are replaced as **whole tokens** only.

**Fastlane `staging_build` signing** (`fastlane/Fastfile`):

- **CT bare** (committed `ios/xcconfig/`, `IOS_BUILD_CONFIGURATION` like `Release-Prod`): writes `PROVISIONING_PROFILE_SPECIFIER` and `CODE_SIGN_IDENTITY` into the matching `ios/xcconfig/{Flavor}.{Debug|Release}.xcconfig` file referenced by the app target.
- **Expo committed-native** (no `ios/xcconfig/`, plain `Debug` / `Release`): skips xcconfig write; uses `xcargs` + `export_options[:provisioningProfiles]` for manual signing.

## Secrets

Provisioning profiles and Firebase app IDs must match the **bootstrapped** bundle IDs (prod = base, dev = `.dev`).

### Firebase client config (not committed)

Do **not** commit `google-services.json` or `GoogleService-Info.plist`. CI restores them from GitHub Actions secrets before native builds:

| Secret | CI use |
| --- | --- |
| `GOOGLE_SERVICES_JSON` | Android — one file may list all flavor `package_name` clients |
| `GOOGLE_SERVICE_INFO_PLIST_DEV` | iOS dev/QA (`Debug-Dev`, `firebase_ios_app: dev`) |
| `GOOGLE_SERVICE_INFO_PLIST_DIST` | iOS prod (`Release-Prod`, TestFlight, `firebase_ios_app: dist`) |

Copy [`.github/firebase-client-paths.example.json`](../.github/firebase-client-paths.example.json) to `.github/firebase-client-paths.json` and set paths for your app target folders. Local dev: copy [`google-services.json.example`](../google-services.json.example) / [`GoogleService-Info.plist.example`](../GoogleService-Info.plist.example) to the real filenames (never commit reals).
