#!/usr/bin/env python3
"""
Rewrite template-specific iOS/Android identifiers in .github/workflows after
copying this kit into another React Native repository.

Expects CT-parity iOS layout (Dev/QA/Prod schemes, ios/xcconfig/*, Release-Prod).
See docs/CI_FLAVOR_CONTRACT.md.

Run from the target app root (where android/ and optionally ios/ live).

Examples:
  python3 .github/scripts/bootstrap_rn_workflow_ids.py --dry-run
  python3 .github/scripts/bootstrap_rn_workflow_ids.py
  python3 .github/scripts/bootstrap_rn_workflow_ids.py --workspace ios/MyApp.xcworkspace --scheme Dev \\
      --bundle-id-dev com.example.app.dev --bundle-id-dist com.example.app
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Template literals shipped with this kit (replace in workflow YAML only).
OLD_WS = "ios/TemplatePipelineReactNative.xcworkspace"
OLD_XCODEPROJ = "ios/TemplatePipelineReactNative.xcodeproj"
OLD_BUILD_IPA = "build/template-pipeline-react-native.ipa"
OLD_IPA_FILENAME = "template-pipeline-react-native.ipa"
OLD_IPA_XCODE_STEM = "TemplatePipelineReactNative.ipa"
OLD_SCHEME = "Dev"
OLD_SCHEME_PROD = "Prod"
OLD_BUNDLE_DEV = "com.codeandtheory.templatepipelinetest.dev"
OLD_BUNDLE_DIST = "com.codeandtheory.templatepipelinetest"
OLD_APP_FOLDER = "ios/TemplatePipelineReactNative"
# android-perf in rn.yml (template sample app — rewritten from android/app/build.gradle on kit apply)
OLD_ANDROID_PACKAGE_DEV = "com.codeandtheory.templaternpipeline.dev"
OLD_ANDROID_ACTIVITY = (
    "com.codeandtheory.templaternpipeline.dev/com.codeandtheory.templaternpipeline.MainActivity"
)
OLD_ARTIFACT = "Dev-iphonesimulator-Debug-Dev"
OLD_IOS_BUILD_CONFIG_DEV = "Debug-Dev"
OLD_IOS_BUILD_CONFIG_DIST = "Release-Prod"
OLD_GRADLE_TASK_DEV = "assembleDevRelease"
OLD_GRADLE_TASK_PROD = "assembleProdRelease"
OLD_APK_GLOB_DEV = "app/build/outputs/apk/dev/release/*.apk"
OLD_APK_GLOB_PROD = "app/build/outputs/apk/prod/release/*.apk"

IOS_SCHEME_INPUT_DEFAULT_RE = re.compile(
    r"(\bios_scheme:\s*\n(?:[ \t]+[^\n]+\n)*?[ \t]+default:\s*)(Dev|Prod)\b"
)


def find_ios_workspaces(ios_dir: Path) -> list[Path]:
    return sorted(p for p in ios_dir.glob("*.xcworkspace") if p.is_dir())


def find_app_xcodeproj(ios_dir: Path, workspace_stem: str) -> Path | None:
    candidates = [p for p in ios_dir.glob("*.xcodeproj") if p.is_dir() and not p.name.startswith("Pods")]
    if not candidates:
        return None
    for p in candidates:
        if p.stem == workspace_stem:
            return p
    if len(candidates) == 1:
        return candidates[0]
    return None


def list_shared_schemes(xcodeproj: Path) -> list[str]:
    schemes_dir = xcodeproj / "xcshareddata" / "xcschemes"
    if not schemes_dir.is_dir():
        return []
    names: list[str] = []
    for f in sorted(schemes_dir.glob("*.xcscheme")):
        if f.name.startswith("Pods-"):
            continue
        names.append(f.stem)
    return names


def has_flavor_build_configs(pbxproj: Path) -> bool:
    text = pbxproj.read_text(encoding="utf-8", errors="replace")
    return "Release-Prod" in text and "Debug-Dev" in text


def bundle_id_from_xcconfig(xcconfig_path: Path) -> str | None:
    if not xcconfig_path.is_file():
        return None
    text = xcconfig_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"PRODUCT_BUNDLE_IDENTIFIER\s*=\s*([^\s;]+)", text)
    return m.group(1).strip() if m else None


def bundle_ids_from_pbxproj(pbxproj: Path) -> tuple[str | None, str | None]:
    text = pbxproj.read_text(encoding="utf-8", errors="replace")
    found: list[str] = []
    for m in re.finditer(
        r"PRODUCT_BUNDLE_IDENTIFIER\s*=\s*(?:\"([^\"]+)\"|([^;\s]+)\s*;)",
        text,
    ):
        val = (m.group(1) or m.group(2) or "").strip()
        if not val or "Tests" in val:
            continue
        if val not in found:
            found.append(val)

    dev = next((b for b in found if b.endswith(".dev") or ".dev" in b), None)
    dist = next((b for b in found if b.endswith(".dist") or ".dist" in b), None)
    qa = next((b for b in found if b.endswith(".qa") or ".qa" in b), None)
    if dev and not dist:
        base_candidates = [b for b in found if b != dev and b != qa and not b.endswith(".dist")]
        if len(base_candidates) == 1:
            dist = base_candidates[0]
    if dev and not dist and len(found) == 2:
        dist = next((b for b in found if b != dev), None)
    if not dev and found:
        dev = found[0]
    if not dist and len(found) > 1:
        dist = next((b for b in found if b != dev and b != qa), None)
    return dev, dist


def bundle_ids_for_ci(ios_dir: Path, pbxproj: Path) -> tuple[str | None, str | None]:
    dev_xc = bundle_id_from_xcconfig(ios_dir / "xcconfig" / "Dev.Release.xcconfig")
    dist_xc = bundle_id_from_xcconfig(ios_dir / "xcconfig" / "Prod.Release.xcconfig")
    if dev_xc or dist_xc:
        b_dev, b_dist = bundle_ids_from_pbxproj(pbxproj)
        return dev_xc or b_dev, dist_xc or b_dist
    return bundle_ids_from_pbxproj(pbxproj)


def pick_schemes(scheme_names: list[str], proj_stem: str) -> tuple[str, str]:
    """Return (dev_scheme, prod_scheme) for CT-parity Dev/Prod or legacy fallbacks."""
    if not scheme_names:
        raise ValueError("No shared .xcscheme files under xcshareddata/xcschemes")

    if "Dev" in scheme_names and "Prod" in scheme_names:
        return "Dev", "Prod"

    prod_candidates = [s for s in scheme_names if s.endswith("_prod") or s.endswith("Prod")]
    dev_candidates = [s for s in scheme_names if s not in prod_candidates]

    prod = None
    if prod_candidates:
        for s in prod_candidates:
            if s == "Prod":
                prod = s
                break
        if prod is None:
            for s in prod_candidates:
                if s.startswith(proj_stem):
                    prod = s
                    break
        prod = prod or prod_candidates[0]

    dev = None
    if "Dev" in dev_candidates:
        dev = "Dev"
    else:
        for s in dev_candidates:
            if s == proj_stem:
                dev = s
                break
        if dev is None and dev_candidates:
            dev = dev_candidates[0]
    if dev is None:
        dev = scheme_names[0]

    if prod is None:
        guess = f"{dev}_prod"
        if guess in scheme_names:
            prod = guess
        elif "Prod" in scheme_names:
            prod = "Prod"
        else:
            prod = dev

    return dev, prod


def read_android_build_gradle(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    kts = path.with_suffix(".gradle.kts")
    if kts.is_file():
        return kts.read_text(encoding="utf-8", errors="replace")
    raise FileNotFoundError(f"Missing {path} and {kts}")


def android_has_dev_flavor(content: str) -> bool:
    return bool(re.search(r"productFlavors\s*\{[\s\S]*?\bdev\s*\{", content))


def android_has_prod_flavor(content: str) -> bool:
    return bool(re.search(r"productFlavors\s*\{[\s\S]*?\bprod\s*\{", content))


def android_gradle_ci_values(
    has_dev: bool,
    has_prod: bool,
    gradle_task_dev_override: str | None = None,
    gradle_task_prod_override: str | None = None,
    apk_glob_dev_override: str | None = None,
    apk_glob_prod_override: str | None = None,
) -> tuple[str, str, str, str]:
    """Derive Gradle tasks and APK globs from productFlavors only (not iOS scheme names)."""
    gradle_task_dev = gradle_task_dev_override or (
        OLD_GRADLE_TASK_DEV if has_dev else "assembleRelease"
    )
    gradle_task_prod = gradle_task_prod_override or (
        OLD_GRADLE_TASK_PROD if has_prod else gradle_task_dev
    )
    apk_glob_dev = apk_glob_dev_override or (
        OLD_APK_GLOB_DEV if has_dev else "app/build/outputs/apk/release/*.apk"
    )
    apk_glob_prod = apk_glob_prod_override or (
        OLD_APK_GLOB_PROD if has_prod else apk_glob_dev
    )
    return gradle_task_dev, gradle_task_prod, apk_glob_dev, apk_glob_prod


def android_dev_application_id(content: str) -> str | None:
    m = re.search(
        r"\bdev\s*\{[\s\S]*?applicationId\s+[\"']([^\"']+)[\"']",
        content,
        re.MULTILINE,
    )
    return m.group(1).strip() if m else None


def android_namespace(content: str) -> str | None:
    m = re.search(r'namespace\s+["\']([^"\']+)["\']', content)
    return m.group(1).strip() if m else None


def android_perf_launcher_component(dev_application_id: str, namespace: str) -> str:
    """adb am start -n component: {applicationId}/{namespace}.MainActivity"""
    return f"{dev_application_id}/{namespace}.MainActivity"


def apply_replacements(text: str, mapping: list[tuple[str, str]]) -> str:
    for old, new in mapping:
        if old != new:
            text = text.replace(old, new)
    return text


def patch_text_ios_scheme_snippets(text: str, scheme_dev: str, scheme_prod: str) -> str:
    if scheme_dev != OLD_SCHEME:
        text = re.sub(r"\bios_scheme:\s*Dev\b", f"ios_scheme: {scheme_dev}", text)
        text = re.sub(r"\bIOS_SCHEME:\s*Dev\b", f"IOS_SCHEME: {scheme_dev}", text)
        text = re.sub(r"\bSCHEME:\s*Dev\b", f"SCHEME: {scheme_dev}", text)

    if scheme_prod != OLD_SCHEME_PROD:
        text = re.sub(r"\bios_scheme:\s*Prod\b", f"ios_scheme: {scheme_prod}", text)

    if scheme_dev != OLD_SCHEME or scheme_prod != OLD_SCHEME_PROD:

        def _scheme_input_default(match: re.Match[str]) -> str:
            prefix = match.group(1)
            token = match.group(2)
            return prefix + (scheme_dev if token == OLD_SCHEME else scheme_prod)

        text = IOS_SCHEME_INPUT_DEFAULT_RE.sub(_scheme_input_default, text)

    return text


def patch_ios_scheme_snippets(
    workflow_dir: Path,
    scheme_dev: str,
    scheme_prod: str,
    dry_run: bool,
) -> list[str]:
    touched: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        orig = text
        text = patch_text_ios_scheme_snippets(text, scheme_dev, scheme_prod)
        if text != orig:
            touched.append(path.name)
            if not dry_run:
                path.write_text(text, encoding="utf-8")
    return touched


def patch_text_android_gradle_snippets(
    text: str,
    gradle_task_dev: str,
    gradle_task_prod: str,
    apk_glob_dev: str,
    apk_glob_prod: str,
) -> str:
    text = re.sub(
        r"gradle_task:\s*assembleDevRelease\b",
        f"gradle_task: {gradle_task_dev}",
        text,
    )
    text = re.sub(
        r"default:\s*assembleProdRelease\b",
        f"default: {gradle_task_prod}",
        text,
    )
    text = re.sub(
        r'default:\s*"assembleDevRelease"',
        f'default: "{gradle_task_dev}"',
        text,
    )
    text = re.sub(
        r"artifact_glob:\s*app/build/outputs/apk/dev/release/\*\.apk\b",
        f"artifact_glob: {apk_glob_dev}",
        text,
    )
    text = re.sub(
        r"default:\s*app/build/outputs/apk/prod/release/\*\.apk\b",
        f"default: {apk_glob_prod}",
        text,
    )
    text = re.sub(
        r"default:\s*\"android/app/build/outputs/apk/dev/release/\*\.apk\"",
        f'default: "android/{apk_glob_dev}"',
        text,
    )
    text = re.sub(
        r"\./gradlew assembleProdRelease\b",
        f"./gradlew {gradle_task_prod}",
        text,
    )
    text = re.sub(
        r"\./gradlew assembleDevRelease\b",
        f"./gradlew {gradle_task_dev}",
        text,
    )
    return text


def patch_android_gradle_snippets(
    workflow_dir: Path,
    gradle_task_dev: str,
    gradle_task_prod: str,
    apk_glob_dev: str,
    apk_glob_prod: str,
    dry_run: bool,
) -> list[str]:
    touched: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        orig = text
        text = patch_text_android_gradle_snippets(
            text, gradle_task_dev, gradle_task_prod, apk_glob_dev, apk_glob_prod
        )
        if text != orig:
            touched.append(path.name)
            if not dry_run:
                path.write_text(text, encoding="utf-8")
    return touched


def replace_in_workflows(workflow_dir: Path, mapping: list[tuple[str, str]], dry_run: bool) -> list[str]:
    changed: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        orig = text
        text = apply_replacements(text, mapping)
        if text != orig:
            changed.append(path.name)
            if not dry_run:
                path.write_text(text, encoding="utf-8")
    return changed


def fastfile_targeted_replacements(
    ws_stem: str,
    ws_rel: str,
    scheme_dev: str,
    scheme_prod: str,
) -> list[tuple[str, str]]:
    new_xcodeproj_rel = f"ios/{ws_stem}.xcodeproj"
    ipa_filename = f"{ws_stem}.ipa"
    new_app_folder = f"ios/{ws_stem}"
    return [
        (OLD_WS, ws_rel),
        (OLD_XCODEPROJ, new_xcodeproj_rel),
        (OLD_BUILD_IPA, f"build/{ipa_filename}"),
        (OLD_IPA_FILENAME, ipa_filename),
        (OLD_APP_FOLDER, new_app_folder),
        (f'../{OLD_APP_FOLDER}/', f"../{new_app_folder}/"),
        ('ENV.fetch("IOS_SCHEME", "Prod")', f'ENV.fetch("IOS_SCHEME", "{scheme_prod}")'),
        ('ENV.fetch("IOS_SCHEME", "Dev")', f'ENV.fetch("IOS_SCHEME", "{scheme_dev}")'),
        (OLD_IPA_XCODE_STEM, ipa_filename),
        (f'output_name: "{OLD_IPA_XCODE_STEM}"', f'output_name: "{ipa_filename}"'),
    ]


def patch_fastfile_targeted(
    root: Path,
    ws_stem: str,
    ws_rel: str,
    scheme_dev: str,
    scheme_prod: str,
    dry_run: bool,
) -> bool:
    path = root / "fastlane" / "Fastfile"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    orig = text
    mapping = fastfile_targeted_replacements(ws_stem, ws_rel, scheme_dev, scheme_prod)
    text = apply_replacements(text, mapping)
    if text == orig:
        return False
    if not dry_run:
        path.write_text(text, encoding="utf-8")
    return True


def patch_android_perf_snippets(
    workflow_dir: Path,
    package_dev: str,
    activity: str,
    dry_run: bool,
) -> list[str]:
    """Rewrite android-perf package/activity in rn.yml from the target app's Gradle IDs."""
    touched: list[str] = []
    path = workflow_dir / "rn.yml"
    if not path.is_file():
        return touched
    text = path.read_text(encoding="utf-8")
    orig = text
    text = re.sub(
        r'(^\s+package:\s+)"[^"]*"',
        rf'\1"{package_dev}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r'(^\s+activity:\s+)"[^"]*"',
        rf'\1"{activity}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if text != orig:
        touched.append("rn.yml (android-perf)")
        if not dry_run:
            path.write_text(text, encoding="utf-8")
    return touched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    ap.add_argument("--workspace", help="Relative path to .xcworkspace (default: auto-detect under ios/).")
    ap.add_argument("--scheme", help="Dev iOS scheme (default: auto-detect, prefers Dev).")
    ap.add_argument("--ios-scheme-prod", help="Prod/dist iOS scheme (default: auto-detect, prefers Prod).")
    ap.add_argument("--bundle-id-dev", help="iOS dev bundle id (default: from xcconfig or Xcode project).")
    ap.add_argument("--bundle-id-dist", help="iOS prod bundle id (default: from xcconfig or Xcode project).")
    ap.add_argument(
        "--gradle-task",
        help="Gradle task for dev Android Firebase job (default: assembleDevRelease if dev flavor exists, else assembleRelease).",
    )
    ap.add_argument(
        "--apk-glob",
        help="APK glob for dev Android Firebase job (default matches --gradle-task).",
    )
    args = ap.parse_args()

    root = Path.cwd()
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        print("error: .github/workflows not found — run from app repository root", file=sys.stderr)
        return 1

    ios_dir = root / "ios"
    if not ios_dir.is_dir():
        print(
            "error: ios/ not found — generate native projects (e.g. expo prebuild) or pass explicit --workspace/--scheme/--bundle-id-*",
            file=sys.stderr,
        )
        return 1

    if args.workspace:
        ws_rel = args.workspace.strip().lstrip("./")
        ws_path = root / ws_rel
        if not ws_path.is_dir():
            print(f"error: workspace not found: {ws_path}", file=sys.stderr)
            return 1
        ws_stem = ws_path.stem
    else:
        wss = find_ios_workspaces(ios_dir)
        if len(wss) != 1:
            print(
                "error: expected exactly one ios/*.xcworkspace; use --workspace\n"
                f"  found: {[p.name for p in wss]}",
                file=sys.stderr,
            )
            return 1
        ws_path = wss[0]
        ws_rel = str(ws_path.relative_to(root))
        ws_stem = ws_path.stem

    xcodeproj = find_app_xcodeproj(ios_dir, ws_stem)
    if xcodeproj is None:
        print("error: could not locate app .xcodeproj under ios/", file=sys.stderr)
        return 1

    pbx = xcodeproj / "project.pbxproj"
    flavor_project = has_flavor_build_configs(pbx)
    if (ios_dir / "xcconfig").is_dir() and not flavor_project:
        print(
            "warning: ios/xcconfig/ exists but Release-Prod not found in project.pbxproj — "
            "CI may need manual flavor setup",
            file=sys.stderr,
        )

    scheme_names = list_shared_schemes(xcodeproj)
    try:
        auto_dev, auto_prod = pick_schemes(scheme_names, xcodeproj.stem)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    scheme_dev = args.scheme or auto_dev
    scheme_prod = args.ios_scheme_prod or auto_prod

    b_dev_auto, b_dist_auto = bundle_ids_for_ci(ios_dir, pbx)
    bundle_dev = args.bundle_id_dev or b_dev_auto
    bundle_dist = args.bundle_id_dist or b_dist_auto
    if not bundle_dev:
        print("error: could not infer dev bundle id — pass --bundle-id-dev", file=sys.stderr)
        return 1
    if not bundle_dist:
        if bundle_dev.endswith(".dev"):
            bundle_dist = bundle_dev[: -len(".dev")]
        else:
            bundle_dist = bundle_dev

    ios_build_config_dev = OLD_IOS_BUILD_CONFIG_DEV if flavor_project else "Debug"
    ios_build_config_dist = OLD_IOS_BUILD_CONFIG_DIST if flavor_project else "Release"

    gradle_path = root / "android" / "app" / "build.gradle"
    try:
        gtext = read_android_build_gradle(gradle_path)
    except FileNotFoundError:
        gtext = ""
    has_dev = android_has_dev_flavor(gtext) if gtext else False
    has_prod = android_has_prod_flavor(gtext) if gtext else False
    gradle_task_dev, gradle_task_prod, apk_glob_dev, apk_glob_prod = android_gradle_ci_values(
        has_dev,
        has_prod,
        gradle_task_dev_override=args.gradle_task,
        apk_glob_dev_override=args.apk_glob,
    )

    artifact_name = f"{scheme_dev}-iphonesimulator-{ios_build_config_dev}"
    ipa_filename = f"{ws_stem}.ipa"

    # Safe global mapping — no bare Dev/Prod scheme tokens (see docs/CI_FLAVOR_CONTRACT.md).
    new_app_folder = f"ios/{ws_stem}"
    mapping: list[tuple[str, str]] = [
        (OLD_WS, ws_rel),
        (OLD_XCODEPROJ, f"ios/{ws_stem}.xcodeproj"),
        (OLD_BUILD_IPA, f"build/{ipa_filename}"),
        (OLD_IPA_FILENAME, ipa_filename),
        (OLD_IPA_XCODE_STEM, ipa_filename),
        (f"build/{OLD_IPA_XCODE_STEM}", f"build/{ipa_filename}"),
        (OLD_APP_FOLDER, new_app_folder),
        (OLD_ARTIFACT, artifact_name),
        (OLD_BUNDLE_DEV, bundle_dev),
        (OLD_BUNDLE_DIST, bundle_dist),
        (OLD_IOS_BUILD_CONFIG_DEV, ios_build_config_dev),
        (OLD_IOS_BUILD_CONFIG_DIST, ios_build_config_dist),
    ]

    print("Detected / using:")
    print(f"  ios_workspace: {ws_rel}")
    print(f"  ios_scheme (dev): {scheme_dev}")
    print(f"  ios_scheme (prod): {scheme_prod}")
    print(f"  bundle_id_dev: {bundle_dev}")
    print(f"  bundle_id_dist: {bundle_dist}")
    print(f"  ios_build_configuration (dev): {ios_build_config_dev}")
    print(f"  ios_build_configuration (dist): {ios_build_config_dist}")
    print(f"  android_dev gradle_task: {gradle_task_dev}")
    print(f"  android_prod gradle_task: {gradle_task_prod}")
    print(f"  android_dev artifact_glob: {apk_glob_dev}")
    print(f"  android_prod artifact_glob: {apk_glob_prod}")
    android_package_dev = OLD_ANDROID_PACKAGE_DEV
    android_activity = OLD_ANDROID_ACTIVITY
    if gtext:
        aid = android_dev_application_id(gtext)
        ns = android_namespace(gtext)
        if aid:
            android_package_dev = aid
            print(f"  android dev applicationId (gradle): {aid}")
        if ns and aid:
            android_activity = android_perf_launcher_component(aid, ns)
            print(f"  android-perf activity component: {android_activity}")
        elif aid:
            print(
                "warning: could not read android namespace — android-perf activity left unchanged; "
                "set package/activity manually in rn.yml",
                file=sys.stderr,
            )

    changed = replace_in_workflows(wf_dir, mapping, args.dry_run)
    scheme_touched = patch_ios_scheme_snippets(wf_dir, scheme_dev, scheme_prod, args.dry_run)
    android_touched = patch_android_gradle_snippets(
        wf_dir, gradle_task_dev, gradle_task_prod, apk_glob_dev, apk_glob_prod, args.dry_run
    )
    perf_touched = patch_android_perf_snippets(
        wf_dir, android_package_dev, android_activity, args.dry_run
    )
    fastlane_touched = patch_fastfile_targeted(
        root, ws_stem, ws_rel, scheme_dev, scheme_prod, args.dry_run
    )

    mode = "Would update" if args.dry_run else "Updated"
    print(f"\n{mode} workflow files (string replacements): {', '.join(changed) or '(none)'}")
    print(f"{mode} iOS scheme snippets: {', '.join(scheme_touched) or '(none)'}")
    print(f"{mode} Android Gradle snippets: {', '.join(android_touched) or '(none)'}")
    print(f"{mode} android-perf package/activity: {', '.join(perf_touched) or '(none)'}")
    print(f"{mode} fastlane/Fastfile: {'yes' if fastlane_touched else '(unchanged or missing)'}")

    if args.dry_run and (
        changed or scheme_touched or android_touched or perf_touched or fastlane_touched
    ):
        print("\nRe-run without --dry-run to apply.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
