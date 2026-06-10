---
name: rn-devops-apply-kit
description: >-
  Apply the RN DevOps kit / pipeline CI to the current React Native app
  (template-pipeline-react-native): user says e.g. "apply the RN DevOps kit",
  "add GitHub Actions from the pipeline template", "copy RN CI workflows here",
  "set up pipeline template CI", plus PATH to the template clone. Low-token,
  shell-first: optional one-message skill-first rsync, then rsync
  .github/.semgrep/.cursor, Gemfile/Fastfile when missing or with explicit
  overwrite, merge .gitignore, align package.json CI scripts, bootstrap
  workflow IDs, Android perf FPS scroll setup (deep link), secrets checklist,
  optional Expo native-dir assert. Use for one-shot pipeline reuse,
  CURSOR_RN_DEVOPS_ONE_SHOT, or copying RN CI from the template.
---

# RN DevOps kit — apply into this repo

Phased playbook for the **target** app (workspace root has `package.json`). Full narrative: [`docs/RN_WORKFLOW_REUSE.md`](../../../docs/RN_WORKFLOW_REUSE.md). Human paste fallback: [`CURSOR_RN_DEVOPS_ONE_SHOT_APPLY.txt`](../../../CURSOR_RN_DEVOPS_ONE_SHOT_APPLY.txt) at the template repo root.

**Minimal user message:** a short intent line plus **`PATH: /absolute/path/to/template-pipeline-react-native`** (no trailing slash). Treat **`PATH:`** the same as **`TEMPLATE_ROOT`** for all commands below. Legacy **`TEMPLATE_ROOT=/…`** and env **`TEMPLATE_ROOT`** or **`RN_PIPELINE_TEMPLATE_ROOT`** are also accepted.

**Prefer this skill** when `.cursor/` is already in the workspace or will be synced by rsync (so routing stays stable). Use the one-shot `.txt` only when the agent cannot load repo skills.

## Single session (one user message)

Use when the user wants **no second chat**: copy this skill (and Cursor rules) from `TEMPLATE_ROOT` onto disk first, optionally load this file into context, then continue **Phase 1** through **Phase 8** (including **Phase 5.5**) in the **same** agent turn.

**Phase 0 — Skill and rules on disk** (from target repo root, `TEMPLATE_ROOT` set):

```bash
mkdir -p .cursor/skills .cursor/rules
rsync -a "${TEMPLATE_ROOT}/.cursor/skills/rn-devops-apply-kit/" "./.cursor/skills/rn-devops-apply-kit/"
rsync -a "${TEMPLATE_ROOT}/.cursor/rules/" "./.cursor/rules/"
```

**Optional (recommended):** `read_file` **`./.cursor/skills/rn-devops-apply-kit/SKILL.md`** once so the phase list is in context. Do **not** bulk-read `.github/workflows/`.

**Then:** run **Phase 1** onward. **Phase 2** must still run the full **`rsync "${TEMPLATE_ROOT}/.cursor/" "./.cursor/"`** (and `.github/`, `.semgrep/`) per [`SETUP_RN_DEVOPS_KIT.md`](../../../SETUP_RN_DEVOPS_KIT.md) — it is idempotent and keeps the whole `.cursor/` tree aligned with the template. **Phase 2.5** (workflow flavor prune) is mandatory after Phase 2.

**Phase 5.5 is mandatory** when `rn.yml` contains **`android-perf`**: use **AskQuestion** (see below) so the user configures FPS on a scrollable screen before handoff.

---

## User inputs (paste in chat before or at start)

| Input | Required | Notes |
| --- | --- | --- |
| Template path | Yes | **`PATH: /absolute/.../template-pipeline-react-native`** (canonical) or **`TEMPLATE_ROOT=/…`** (legacy). Strip trailing slashes. |
| `TARGET_REMOTE_URL` | No | HTTPS/SSH of an empty GitHub repo if you want remote + push after commit. |
| Bootstrap CLI flags | No | Only if dry-run is wrong: `--workspace`, `--scheme`, `--bundle-id-dev`, `--bundle-id-dist`, `--gradle-task`, `--apk-glob` (see [`docs/RN_WORKFLOW_REUSE.md`](../../../docs/RN_WORKFLOW_REUSE.md)). |

**Resolve `TEMPLATE_ROOT` before preflight:** (1) If the user message contains **`PATH:`**, set `TEMPLATE_ROOT` to the trimmed path after `PATH:` (first line wins). (2) Else if **`TEMPLATE_ROOT=`** appears, use that value. (3) Else if env **`TEMPLATE_ROOT`** or **`RN_PIPELINE_TEMPLATE_ROOT`** is set, use it. (4) Else stop and ask once for **`PATH:`** or **`TEMPLATE_ROOT=`**.

Agent preflight: `test -d "${TEMPLATE_ROOT}/.github" && test -f "${TEMPLATE_ROOT}/SETUP_RN_DEVOPS_KIT.md"` (shell only; do not read the template tree into context).

---

## Token efficiency (read this first)

1. **Shell-first** — Use `rsync`, `cp`, `python3`, and small `node` / `jq` snippets. Do **not** bulk-`read_file` under `.github/workflows/`, template `.github/`, `node_modules/`, `ios/Pods/`, or coverage output.
2. **Bootstrap / secrets** — Treat **`python3 .github/scripts/bootstrap_rn_workflow_ids.py`** and **`list_workflow_secrets.py`** stdout as truth; do not open every modified YAML in the editor to “verify”.
3. **`.gitignore`** — Merge with a shell loop (below); do not paste the full `.gitignore` into chat unless the user asks for a review.
4. **`package.json` scripts** — Add missing CI script **names** with the embedded **`node` heredoc** below (local file only); do not read the template’s `package.json` into context. If **`yarn.lock`** exists and **`actions/setup-node`** cache fails later, see **Yarn-only** in [`docs/RN_WORKFLOW_REUSE.md`](../../../docs/RN_WORKFLOW_REUSE.md) (no need to grep all workflows up front).
5. **`src/`** — Never overwrite unless the user explicitly asks.

---

## AskQuestion — Gemfile / Fastfile overwrite

Run **only if** any of these exist: `./Gemfile`, `./Gemfile.lock`, `./fastlane/Fastfile`. If **none** exist, skip the question and use missing-only copies.

**Prompt:** Overwrite existing root `Gemfile` / `Gemfile.lock` or `fastlane/Fastfile` from the template?

- **Default (recommended):** No — copy `Gemfile`/`Gemfile.lock` only when at least one is missing (`if [ ! -f ./Gemfile ] || [ ! -f ./Gemfile.lock ]; then cp ...`); copy `Fastfile` only when `./fastlane/Fastfile` is missing.
- **Yes:** `cp "${TEMPLATE_ROOT}/Gemfile" "${TEMPLATE_ROOT}/Gemfile.lock" ./` and `mkdir -p fastlane && cp "${TEMPLATE_ROOT}/fastlane/Fastfile" ./fastlane/` unconditionally.

---

## AskQuestion — Android perf FPS scroll (mandatory after Phase 5)

Run when **`.github/workflows/rn.yml`** contains an **`android-perf`** job (always true after kit sync). **Do not skip** unless the user already supplied a deep link and settle time in the same message.

**Prompt 1 — FPS measurement target**

| Option | Meaning |
| --- | --- |
| **Scrollable screen via deep link** | User will provide (or already provided) a URL such as `myapp://posts`; agent runs `configure_android_perf_fps.py` and reminds them to add linking + intent filter per [`docs/ANDROID_PERF_FPS_SETUP.md`](../../../docs/ANDROID_PERF_FPS_SETUP.md). |
| **Launcher / home only** | No deep link; run `configure_android_perf_fps.py --clear`. FPS is measured on whatever screen is open after cold launch (often less representative). |
| **Disable android-perf for now** | Comment out or remove the `android-perf` job in `rn.yml`; tell user they can re-enable after app setup. |

**Prompt 2** (only if **Scrollable screen via deep link**): ask in chat for:

1. **Deep link URL** — must match React Navigation `linking` and Android intent filter.
2. **`perf_settle_seconds`** — default **12** if omitted (network + list render wait).

Then from target repo root:

```bash
python3 .github/scripts/configure_android_perf_fps.py \
  --deep-link "<url-from-user>" \
  --settle-seconds <seconds>
```

**If the scroll screen needs remote data** (e.g. `react-native-config` / `API_BASE_URL`):

- Ensure **`.github/env.dev.ci`** exists (copied with the kit) or create it with safe dev API values.
- Confirm **`android-dev`** runs `ensure_react_native_config_env.sh` (in `rn-job-android-firebase-release.yml` after sync).
- Remind: commit **intent filter** + **linking** in the app; secrets checklist for Firebase if the app uses `@react-native-firebase`.

**Handoff bullet** (always include when `android-perf` is enabled): link [`docs/ANDROID_PERF_FPS_SETUP.md`](../../../docs/ANDROID_PERF_FPS_SETUP.md) and note whether deep link was configured or cleared.

---

## Phase 1 — Preflight

1. Confirm cwd is the app root: `test -f ./package.json`.
2. Resolve and export **`TEMPLATE_ROOT`** per **User inputs** (from **`PATH:`**, **`TEMPLATE_ROOT=`**, or env). Confirm valid with the directory checks above.
3. Run **Optional AskQuestion** when applicable.

---

## Phase 2 — Sync kit

From the target root, same as [`SETUP_RN_DEVOPS_KIT.md`](../../../SETUP_RN_DEVOPS_KIT.md):

```bash
rsync -a --delete "${TEMPLATE_ROOT}/.github/" "./.github/"
rsync -a "${TEMPLATE_ROOT}/.semgrep/" "./.semgrep/"
rsync -a "${TEMPLATE_ROOT}/.cursor/" "./.cursor/"
```

Then **`Gemfile` / `Gemfile.lock`** and **`fastlane/Fastfile`** per the overwrite answer (see **Optional AskQuestion**).

---

## Phase 2.5 — Prune workflows to project flavor (mandatory)

After rsync, keep only workflows for the target app. **Bare** repos get bare-only optional jobs and no EAS files; **Expo (committed native)** repos get `expo-native-dirs` orchestrators and no bare-only or EAS files.

**Detection:** `"expo"` in `package.json` `dependencies` or `devDependencies` → **`expo-committed`**; otherwise **`bare`**. Override with `--flavor bare` or `--flavor expo-committed` if auto-detection is wrong (e.g. only `expo-dev-client` without `expo`).

```bash
python3 .github/scripts/prune_workflows_for_flavor.py --dry-run
python3 .github/scripts/prune_workflows_for_flavor.py
```

Also removes kit metadata from the target repo: **`.github/workflow-orchestrators/`**, **`.github/workflow-manifests/`**, **`validate_workflow_flavor_prune.sh`**, **`eas_extract_build_id.py`**. **Bare** targets also drop **`assert_expo_native_dirs.sh`**. **`prune_workflows_for_flavor.py`** stays (re-run after a fresh kit rsync).

Runs **before** bootstrap and **`list_workflow_secrets.py`** so the secrets checklist matches the pruned workflow set (no **`EXPO_TOKEN`** for committed-native Expo unless EAS workflows were re-added manually).

---

## Phase 3 — Merge `.gitignore`

```bash
touch .gitignore
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  grep -qxF "$line" .gitignore 2>/dev/null || echo "$line" >> .gitignore
done < "${TEMPLATE_ROOT}/GITIGNORE_APPEND.txt"
```

---

## Phase 4 — `package.json` CI scripts (if missing)

Run from target root (adds only missing keys; preserves existing commands):

```bash
node <<'NODE'
const fs = require('fs');
const path = 'package.json';
const pkg = JSON.parse(fs.readFileSync(path, 'utf8'));
pkg.scripts = pkg.scripts || {};
const add = {
  lint: 'eslint .',
  'format:check': 'prettier --check "src/**/*.{ts,tsx,js}"',
  typecheck: 'tsc --noEmit',
  'test:ci': 'jest --ci --coverage --maxWorkers=2',
};
let changed = false;
for (const [k, v] of Object.entries(add)) {
  if (pkg.scripts[k] == null) {
    pkg.scripts[k] = v;
    changed = true;
  }
}
if (changed) fs.writeFileSync(path, JSON.stringify(pkg, null, 2) + '\n');
NODE
```

If any script key was added, remind the user to install matching **devDependencies** (see the scripts table in [`docs/RN_WORKFLOW_REUSE.md`](../../../docs/RN_WORKFLOW_REUSE.md)) if not already present — check with `node -e` / `npm ls` in terminal, not by reading `node_modules/`.

---

## Phase 5 — Bootstrap workflow identifiers

```bash
python3 .github/scripts/bootstrap_rn_workflow_ids.py --dry-run
```

Review terminal output. Then:

```bash
python3 .github/scripts/bootstrap_rn_workflow_ids.py
```

Append any user-provided flags on both commands if detection is wrong. If there is **no `ios/`** or bootstrap cannot resolve the workspace, stop and tell the user to run **`npx expo prebuild --clean`** (Expo), commit **`ios/`** / **`android/`**, or pass documented flags.

**Note:** Bundle IDs are read from **`ios/xcconfig/`** (CT parity) then **`project.pbxproj`**, not from `app.config.ts` alone. CI expects **Dev** + **Debug-Dev** (dev) and **Prod** + **Release-Prod** (dist); prod bundle ID is the **base** id (no `.dist`). See **`docs/CI_FLAVOR_CONTRACT.md`**.

**Android performance (`android-perf` in `rn.yml`):** The template ships sample **`package`** (dev `applicationId`) and **`activity`** (`{applicationId}/{namespace}.MainActivity`) for this repo’s app. Bootstrap reads **`android/app/build.gradle`** and rewrites those two fields — do not hand-edit after apply unless detection failed. If bootstrap warns about a missing namespace, set them manually to match the dev APK you build in **`android-dev`**.

---

## Phase 5.5 — Android perf FPS scroll setup

1. Confirm **`android-perf`** exists in **`.github/workflows/rn.yml`** (if not, skip this phase).
2. Run **AskQuestion — Android perf FPS scroll** (above). Collect deep link URL and settle seconds when applicable.
3. Run **`configure_android_perf_fps.py`** with `--deep-link` / `--settle-seconds` or `--clear`.
4. If the user chose scrollable screen but has not implemented linking yet, list app tasks from **`docs/ANDROID_PERF_FPS_SETUP.md`** (intent filter, `FlatList`, env file) in the Phase 8 handoff — CI will not measure meaningful FPS until those exist.

---

## Phase 6 — Secrets checklist

```bash
python3 .github/scripts/list_workflow_secrets.py --write GITHUB_SECRETS_CHECKLIST.md
```

Remind: secret **values** only in GitHub → Settings → Secrets and variables → Actions (never commit secrets).

---

## Phase 7 — Optional validate (Expo)

If `expo` is in `dependencies` or `devDependencies`, run **`assert_expo_native_dirs.sh`** (validates committed `android/` / `ios/` without reading those trees into context):

```bash
if node -e 'const p=require("./package.json");const d={...p.dependencies||{},...p.devDependencies||{}};process.exit("expo" in d?0:1)'; then
  bash .github/scripts/assert_expo_native_dirs.sh expo
fi
```

---

## Phase 8 — Git and handoff

- If **`TARGET_REMOTE_URL`** was provided: commit with a clear message, set `origin` / push current branch per **`.cursor/rules/git-rn-bootstrap.mdc`** and **`.cursor/rules/rn-devops-agent-playbook.mdc`**. Do not push unless the user supplied the URL and expects it.
- **Handoff:** List manual follow-ups separately: Firebase, keystores, App Store Connect API key, Play service account. **`EXPO_TOKEN`** is not required after flavor prune (EAS workflows removed); only if the team manually restores EAS workflows. Summarize Phase 2.5 flavor (`bare` or `expo-committed`) applied. Keep signing separate from Git remote setup.
- **Android perf FPS:** Summarize Phase 5.5 outcome (deep link configured, cleared, or job disabled) and point to [`docs/ANDROID_PERF_FPS_SETUP.md`](../../../docs/ANDROID_PERF_FPS_SETUP.md) for any remaining app-side work.
