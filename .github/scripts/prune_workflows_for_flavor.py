#!/usr/bin/env python3
"""
Prune GitHub Actions workflows to bare or expo-committed flavor after kit rsync.

Usage (from repository root):
  python3 .github/scripts/prune_workflows_for_flavor.py --dry-run
  python3 .github/scripts/prune_workflows_for_flavor.py
  python3 .github/scripts/prune_workflows_for_flavor.py --flavor bare
  python3 .github/scripts/prune_workflows_for_flavor.py --flavor expo-committed
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

MANIFEST_DIR = Path(".github/workflow-manifests")
ORCHESTRATOR_DIR = Path(".github/workflow-orchestrators")
WORKFLOW_DIR = Path(".github/workflows")
PACKAGE_JSON = Path("package.json")

FLAVOR_BARE = "bare"
FLAVOR_EXPO = "expo-committed"
VALID_FLAVORS = frozenset({FLAVOR_BARE, FLAVOR_EXPO})

ORCHESTRATOR_STEMS = ("rn", "rn-internal-release", "rn-firebase-release")

USES_RE = re.compile(
    r"uses:\s*\./\.github/workflows/([A-Za-z0-9_.-]+\.yml)",
    re.MULTILINE,
)


def read_manifest_list(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line)
    return names


def detect_flavor_from_package_json(package_json: Path = PACKAGE_JSON) -> str:
    if not package_json.is_file():
        print(f"error: {package_json} not found", file=sys.stderr)
        sys.exit(1)
    pkg = json.loads(package_json.read_text(encoding="utf-8"))
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    return FLAVOR_EXPO if "expo" in deps else FLAVOR_BARE


def prune_manifest_path(flavor: str) -> Path:
    return MANIFEST_DIR / f"prune-from-{flavor}.txt"


def orchestrator_source(stem: str, flavor: str) -> Path:
    return ORCHESTRATOR_DIR / f"{stem}.{flavor}.yml"


def orchestrator_dest(stem: str) -> Path:
    return WORKFLOW_DIR / f"{stem}.yml"


def collect_uses_refs(workflow_dir: Path) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        refs[path.name] = set(USES_RE.findall(text))
    return refs


def verify_workflow_refs(workflow_dir: Path) -> list[str]:
    errors: list[str] = []
    existing = {p.name for p in workflow_dir.glob("*.yml")}
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for target in USES_RE.findall(text):
            if target not in existing:
                errors.append(f"{path.name} references missing workflow: {target}")
    return errors


def install_orchestrators(flavor: str, dry_run: bool) -> list[tuple[Path, Path]]:
    installed: list[tuple[Path, Path]] = []
    for stem in ORCHESTRATOR_STEMS:
        src = orchestrator_source(stem, flavor)
        dest = orchestrator_dest(stem)
        if not src.is_file():
            raise FileNotFoundError(f"orchestrator template not found: {src}")
        installed.append((src, dest))
        if dry_run:
            print(f"[dry-run] install orchestrator {src} -> {dest}")
        else:
            shutil.copy2(src, dest)
            print(f"installed orchestrator {dest.name} from {src.name}")
    return installed


def prune_files(flavor: str, dry_run: bool) -> list[str]:
    to_remove = read_manifest_list(prune_manifest_path(flavor))
    removed: list[str] = []
    for name in to_remove:
        path = WORKFLOW_DIR / name
        if not path.is_file():
            print(f"skip (already absent): {name}")
            continue
        if dry_run:
            print(f"[dry-run] remove {path}")
        else:
            path.unlink()
            print(f"removed {name}")
        removed.append(name)
    return removed


def cleanup_manifest_path(name: str) -> Path:
    return MANIFEST_DIR / name


def cleanup_kit_metadata(flavor: str, dry_run: bool) -> list[str]:
    """Remove kit-only paths from target repos after orchestrators are installed."""
    paths: list[str] = []
    for manifest_name in ("cleanup-always.txt", f"cleanup-{flavor}-only.txt"):
        manifest = cleanup_manifest_path(manifest_name)
        if not manifest.is_file():
            continue
        paths.extend(read_manifest_list(manifest))

    removed: list[str] = []
    for rel in paths:
        target = Path(rel)
        if not target.exists():
            print(f"skip (already absent): {rel}")
            continue
        if dry_run:
            print(f"[dry-run] remove {target}")
        elif target.is_dir():
            shutil.rmtree(target)
            print(f"removed directory {rel}")
        else:
            target.unlink()
            print(f"removed {rel}")
        removed.append(rel)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prune workflows and install flavor-specific orchestrators after kit rsync.",
    )
    parser.add_argument(
        "--flavor",
        choices=sorted(VALID_FLAVORS),
        default=None,
        help="bare | expo-committed (default: auto from package.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without modifying files",
    )
    args = parser.parse_args()

    flavor = args.flavor or detect_flavor_from_package_json()
    if flavor not in VALID_FLAVORS:
        print(f"error: invalid flavor {flavor!r}", file=sys.stderr)
        return 1

    print(f"flavor: {flavor}" + (" (auto-detected)" if args.flavor is None else ""))

    if not ORCHESTRATOR_DIR.is_dir():
        print(f"error: {ORCHESTRATOR_DIR} not found — run kit rsync first", file=sys.stderr)
        return 1
    if not WORKFLOW_DIR.is_dir():
        print(f"error: {WORKFLOW_DIR} not found", file=sys.stderr)
        return 1

    install_orchestrators(flavor, args.dry_run)
    removed = prune_files(flavor, args.dry_run)

    if args.dry_run:
        remaining = sorted(p.name for p in WORKFLOW_DIR.glob("*.yml") if p.name not in removed)
        refs = collect_uses_refs(WORKFLOW_DIR)
        errors: list[str] = []
        for name in remaining:
            for target in refs.get(name, set()):
                if target in removed:
                    errors.append(f"{name} references workflow scheduled for removal: {target}")
        if errors:
            print("error: broken references after prune:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        cleanup_kit_metadata(flavor, dry_run=True)
        print(f"[dry-run] would keep {len(remaining)} workflow file(s)")
        return 0

    errors = verify_workflow_refs(WORKFLOW_DIR)
    if errors:
        print("error: broken workflow references after prune:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    cleanup_kit_metadata(flavor, dry_run=False)

    kept = len(list(WORKFLOW_DIR.glob("*.yml")))
    print(f"done: {kept} workflow file(s) remain for flavor {flavor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
