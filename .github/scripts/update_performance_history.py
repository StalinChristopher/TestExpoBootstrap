#!/usr/bin/env python3
"""
Merge extracted metrics into ci/performance-baseline.json and append ci/performance-history.json.
Run on pushes to main after UI performance tests.

Baseline preservation (mirrors Android perf_baselines.json strategy):
  When extracted metrics are empty (extraction failure) and the existing baseline already has
  real metric values, the baseline file is left untouched so previous good numbers are not
  clobbered. The history file still receives an entry flagged with extractionFailed=true.
  Pass --force-update-on-empty to override this guard.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--metrics", required=True, type=Path, help="JSON from extract_performance_metrics.py")
    p.add_argument("--baseline-out", default=Path("ci/performance-baseline.json"), type=Path)
    p.add_argument("--history-out", default=Path("ci/performance-history.json"), type=Path)
    p.add_argument("--max-history", type=int, default=100)
    p.add_argument(
        "--force-update-on-empty",
        action="store_true",
        default=False,
        help="Overwrite existing baseline even when extracted metrics are empty. Default: preserve.",
    )
    args = p.parse_args()

    doc = json.loads(args.metrics.read_text(encoding="utf-8"))
    metrics = doc.get("metrics") or {}

    sha = os.environ.get("GITHUB_SHA", "local")
    now = datetime.now(timezone.utc).isoformat()

    # Preserve an existing non-empty baseline when extraction produced nothing.
    # This mirrors the Android strategy: seed/last-known values stay in place
    # until a real run on main captures live metrics.
    if not metrics and not args.force_update_on_empty:
        existing_metrics: dict = {}
        if args.baseline_out.exists():
            try:
                existing = json.loads(args.baseline_out.read_text(encoding="utf-8"))
                existing_metrics = existing.get("metrics") or {}
            except Exception:
                pass
        if existing_metrics:
            print(
                f"::warning::Extracted metrics are empty — preserving existing baseline at "
                f"{args.baseline_out} (pass --force-update-on-empty to override)."
            )
            _append_history(args.history_out, args.max_history, sha, now, metrics={}, extraction_failed=True)
            return

    baseline = {
        "schemaVersion": 1,
        "updatedAt": now,
        "gitSha": sha,
        "metrics": metrics,
    }
    args.baseline_out.parent.mkdir(parents=True, exist_ok=True)
    args.baseline_out.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    _append_history(args.history_out, args.max_history, sha, now, metrics=metrics)
    print(f"Updated {args.baseline_out} and {args.history_out}")


def _append_history(
    history_out: Path,
    max_history: int,
    sha: str,
    now: str,
    metrics: dict,
    extraction_failed: bool = False,
) -> None:
    history: list = []
    if history_out.exists():
        try:
            history = json.loads(history_out.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []

    entry: dict = {
        "schemaVersion": 1,
        "recordedAt": now,
        "gitSha": sha,
        "metrics": metrics,
    }
    if extraction_failed:
        entry["extractionFailed"] = True

    history.append(entry)
    history = history[-max_history:]
    history_out.parent.mkdir(parents=True, exist_ok=True)
    history_out.write_text(json.dumps(history, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
