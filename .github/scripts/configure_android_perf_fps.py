#!/usr/bin/env python3
"""
Wire android-perf FPS scroll target in rn.yml (deep link + settle time).

Run after bootstrap_rn_workflow_ids.py when applying the RN DevOps kit to a new app.

Examples:
  python3 .github/scripts/configure_android_perf_fps.py \\
    --deep-link myapp://feed --settle-seconds 12

  python3 .github/scripts/configure_android_perf_fps.py --clear
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RN_YML = Path(".github/workflows/rn.yml")
DEEP_LINK_KEY = "deep_link"
SETTLE_KEY = "perf_settle_seconds"


def extract_android_perf_block(text: str) -> tuple[int, int] | None:
    """Return (start, end) line indices for the android-perf job block (inclusive start)."""
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^  android-perf:\s*$", line):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^  [a-z0-9-]+:\s*$", lines[j]):
            end = j
            break
    return start, end


def upsert_with_key(lines: list[str], key: str, value_line: str, indent: str = "      ") -> list[str]:
    """Replace or append a key under android-perf `with:` (6-space indent)."""
    key_prefix = f"{indent}{key}:"
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(key_prefix):
            out.append(value_line if value_line.endswith("\n") else value_line + "\n")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        # Insert before first gates/out_dir comment block or before secrets: inherit sibling
        insert_at = len(out)
        for i, line in enumerate(out):
            if "secrets: inherit" in line:
                insert_at = i
                break
            if re.match(rf"{indent}# ── Gates", line):
                insert_at = i
                break
        out.insert(insert_at, value_line if value_line.endswith("\n") else value_line + "\n")
    return out


def remove_with_keys(lines: list[str], keys: tuple[str, ...], indent: str = "      ") -> list[str]:
    prefixes = tuple(f"{indent}{k}:" for k in keys)
    return [line for line in lines if not line.startswith(prefixes)]


def configure(deep_link: str | None, settle_seconds: float | None, rn_path: Path, dry_run: bool) -> int:
    if not rn_path.is_file():
        print(f"error: {rn_path} not found — run from repository root", file=sys.stderr)
        return 1

    text = rn_path.read_text(encoding="utf-8")
    span = extract_android_perf_block(text)
    if span is None:
        print("error: android-perf job not found in rn.yml", file=sys.stderr)
        return 1

    start, end = span
    lines = text.splitlines(keepends=True)
    block = lines[start:end]

    if deep_link:
        block = remove_with_keys(block, (DEEP_LINK_KEY, SETTLE_KEY))
        settle = settle_seconds if settle_seconds is not None else 12.0
        block = upsert_with_key(
            block,
            DEEP_LINK_KEY,
            f'      {DEEP_LINK_KEY}: "{deep_link}"',
        )
        block = upsert_with_key(
            block,
            SETTLE_KEY,
            f"      {SETTLE_KEY}: {int(settle) if settle == int(settle) else settle}",
        )
        # Ensure comment above FPS keys
        if not any("FPS scroll target" in ln for ln in block):
            for i, line in enumerate(block):
                if line.strip().startswith("apk_artifact_name:"):
                    block.insert(
                        i + 1,
                        "\n      # FPS scroll target — opened before scroll measurement (see docs/ANDROID_PERF_FPS_SETUP.md)\n",
                    )
                    break
        action = f"Set {DEEP_LINK_KEY}={deep_link!r}, {SETTLE_KEY}={settle}"
    else:
        block = remove_with_keys(block, (DEEP_LINK_KEY, SETTLE_KEY))
        action = f"Cleared {DEEP_LINK_KEY} / {SETTLE_KEY} (FPS measured on default screen after launch)"

    new_text = "".join(lines[:start] + block + lines[end:])
    if dry_run:
        print(f"[dry-run] {action}")
        return 0

    rn_path.write_text(new_text, encoding="utf-8")
    print(f"[configure_android_perf_fps] {action}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deep-link", default=None, help="Deep link URL (e.g. myapp://posts). Omit with --clear.")
    ap.add_argument(
        "--settle-seconds",
        type=float,
        default=12.0,
        help="Seconds to wait after opening deep link before FPS scroll (default: 12)",
    )
    ap.add_argument("--clear", action="store_true", help="Remove deep_link / perf_settle_seconds from rn.yml")
    ap.add_argument("--rn-yml", type=Path, default=RN_YML, help="Path to rn.yml (default: .github/workflows/rn.yml)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.clear:
        return configure(None, None, args.rn_yml, args.dry_run)
    if not args.deep_link:
        print("error: pass --deep-link URL or --clear", file=sys.stderr)
        return 1
    return configure(args.deep_link.strip(), args.settle_seconds, args.rn_yml, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
