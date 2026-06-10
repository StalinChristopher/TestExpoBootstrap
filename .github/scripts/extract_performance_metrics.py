#!/usr/bin/env python3
"""
Extract XCTest performance metrics from:
  1) xcresulttool JSON (multiple shapes / legacy + modern)
  2) Optional xcodebuild test log (lines containing "measured [...] average:")
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Map a substring of the raw XCTest metric label (lowercased) to a canonical key.
# Real XCTest labels (Xcode 26): "Duration (AppLaunch), s", "CPU Time, s",
# "Memory Peak Physical, kB". Order matters — first matching needle wins, so more
# specific needles ("memory peak physical") precede broader ones.
DISPLAY_TO_KEY = {
    "applaunch": "launch_duration_seconds",
    "application launch": "launch_duration_seconds",
    "launch": "launch_duration_seconds",
    "cpu time": "cpu_time_seconds",
    "memory peak physical": "memory_peak_mb",
    "memory physical peak": "memory_peak_mb",
    "memory peak": "memory_peak_mb",
}

# Only these three metrics are reported. XCTCPUMetric/XCTMemoryMetric emit several
# sub-metrics (CPU Cycles, Memory Physical, …); restricting to the canonical set keeps
# the PR table aligned with the seed/baseline and avoids noisy "new" rows.
CANONICAL_DISPLAY = {
    "launch_duration_seconds": "Application Launch",
    "cpu_time_seconds": "CPU Time",
    "memory_peak_mb": "Memory Physical Peak",
}
CANONICAL_UNIT = {
    "launch_duration_seconds": "s",
    "cpu_time_seconds": "s",
    "memory_peak_mb": "MB",
}
CANONICAL_KEYS = set(CANONICAL_DISPLAY.keys())


def _normalize_key(display: str | None) -> str | None:
    if not display:
        return None
    lower = display.strip().lower()
    for needle, slug in DISPLAY_TO_KEY.items():
        if needle in lower:
            return slug
    return lower.replace(" ", "_").replace(".", "_").replace("(", "").replace(")", "")


def _to_canonical_value(key: str, median: float, unit: str | None) -> float:
    """Convert a raw median into the canonical unit for the metric.

    Memory metrics are emitted by XCTMemoryMetric in kB; the seed/baseline track MB.
    Launch/CPU are already in seconds.
    """
    if key != "memory_peak_mb":
        return round(median, 3)
    u = (unit or "").strip().lower()
    if u in ("kb", "kib"):
        return round(median / 1024.0, 3)
    if u in ("b", "byte", "bytes"):
        return round(median / (1024.0 * 1024.0), 3)
    if u in ("gb", "gib"):
        return round(median * 1024.0, 3)
    # Already MB (or unknown) — assume MB.
    return round(median, 3)


def _unit_from_label(label: str) -> str | None:
    """Derive the unit from a measured-line label like 'Memory Peak Physical, kB'."""
    if "," in label:
        return label.rsplit(",", 1)[1].strip() or None
    return None


def _coerce_measurement_values(measurements: Any) -> list[float]:
    if measurements is None:
        return []
    if isinstance(measurements, list):
        return [float(x) for x in measurements if isinstance(x, (int, float))]
    if isinstance(measurements, dict):
        vals = measurements.get("_values")
        if isinstance(vals, list):
            return [float(x) for x in vals if isinstance(x, (int, float))]
        stats = measurements.get("statistics") or measurements.get("Statistics")
        if isinstance(stats, dict) and "median" in stats:
            return [float(stats["median"])]
    return []


def _median_from_values(nums: list[float]) -> float | None:
    if not nums:
        return None
    nums = sorted(nums)
    mid = len(nums) // 2
    if len(nums) % 2:
        return nums[mid]
    return (nums[mid - 1] + nums[mid]) / 2


def _median_from_metric_blob(blob: dict[str, Any]) -> tuple[float | None, str | None, str | None]:
    name = (
        blob.get("displayName")
        or blob.get("name")
        or blob.get("identifier")
        or blob.get("title")
    )
    if isinstance(name, dict):
        name = name.get("_value") or name.get("displayName")

    unit = blob.get("unitOfMeasurement")
    if isinstance(unit, dict):
        unit = unit.get("_value") or unit.get("displayName")

    measurements = blob.get("measurements")
    nums = _coerce_measurement_values(measurements)
    median = _median_from_values(nums)

    if median is None and isinstance(measurements, dict):
        stats = measurements.get("statistics") or measurements.get("Statistics")
        if isinstance(stats, dict) and "median" in stats:
            median = float(stats["median"])

    if median is None:
        for k in ("median", "baselineAverage", "aggregateResult"):
            if k in blob and isinstance(blob[k], (int, float)):
                median = float(blob[k])
                break

    display = str(name) if name else None
    unit_s = str(unit) if unit else None
    return median, display, unit_s


def _walk_original(obj: Any, found: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if "performanceMetrics" in obj and isinstance(obj["performanceMetrics"], dict):
            pm = obj["performanceMetrics"]
            vals = pm.get("_values")
            if isinstance(vals, list):
                for item in vals:
                    if isinstance(item, dict):
                        found.append(item)
        if "performanceMetricResults" in obj and isinstance(obj["performanceMetricResults"], dict):
            pm = obj["performanceMetricResults"]
            vals = pm.get("_values")
            if isinstance(vals, list):
                for item in vals:
                    if isinstance(item, dict):
                        found.append(item)
        for v in obj.values():
            _walk_original(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_original(item, found)


def _walk_typed_summaries(obj: Any, found: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        t = obj.get("_type")
        name = None
        if isinstance(t, dict):
            name = t.get("_name")
        if name in (
            "ActionTestPerformanceMetricSummary",
            "ActionTestPerformanceMetricResult",
            "PerformanceMetric",
        ):
            found.append(obj)
        for v in obj.values():
            _walk_typed_summaries(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_typed_summaries(item, found)


def _walk_display_measurements(obj: Any, found: list[dict[str, Any]], depth: int = 0) -> None:
    if depth > 80:
        return
    if isinstance(obj, dict):
        dn = obj.get("displayName") or obj.get("name")
        if isinstance(dn, dict):
            dn = dn.get("_value")
        has_meas = "measurements" in obj or "measurement" in obj
        if isinstance(dn, str) and has_meas:
            lower = dn.lower()
            if any(k in lower for k in ("launch", "cpu", "memory", "application", "metric")):
                found.append(obj)
        for v in obj.values():
            _walk_display_measurements(v, found, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _walk_display_measurements(item, found, depth + 1)


def load_xcresult_json(xcresult: Path) -> dict[str, Any]:
    last_err = ""
    last_code = 1
    for extra in ([], ["--legacy"]):
        proc = subprocess.run(
            [
                "xcrun",
                "xcresulttool",
                "get",
                *extra,
                "--path",
                str(xcresult),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        last_code = proc.returncode
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
        last_err = proc.stderr or proc.stdout or "xcresulttool failed"
    # Do not abort: newer Xcode (26+) sometimes rejects the JSON export entirely.
    # Return an empty root so the xcodebuild-log fallback (measured-average lines)
    # can still populate metrics.
    sys.stderr.write(
        f"::warning::xcresulttool could not export JSON (exit {last_code}): "
        f"{last_err.strip()[:200]} — falling back to xcodebuild log parsing.\n"
    )
    return {}


def _merge_blobs(root: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    merged: list[dict[str, Any]] = []

    def collect(batch: list[dict[str, Any]]) -> None:
        for b in batch:
            bid = id(b)
            if bid in seen:
                continue
            seen.add(bid)
            merged.append(b)

    b1: list[dict[str, Any]] = []
    _walk_original(root, b1)
    collect(b1)
    b2: list[dict[str, Any]] = []
    _walk_typed_summaries(root, b2)
    collect(b2)
    b3: list[dict[str, Any]] = []
    _walk_display_measurements(root, b3)
    collect(b3)
    return merged


# XCTest / xcodebuild lines like:
# measured [Time (Application Launch), s] average: 0.842, ...
# measured [CPU Time, s] average: ...
_MEASURED_AVG = re.compile(
    r"measured\s+\[([^\]]+)\][^\n]*?average:\s*([\d.]+)",
    re.IGNORECASE,
)
_MEASURED_MEDIAN = re.compile(
    r"measured\s+\[([^\]]+)\][^\n]*?median:\s*([\d.]+)",
    re.IGNORECASE,
)


def parse_xcodebuild_log(log_path: Path) -> dict[str, Any]:
    """Fallback when xcresult JSON omits performance metric blobs."""
    if not log_path.exists():
        return {}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    metrics: dict[str, Any] = {}
    for rx in (_MEASURED_AVG, _MEASURED_MEDIAN):
        for match in rx.finditer(text):
            raw_label = match.group(1).strip()
            val = float(match.group(2))
            nk = _normalize_key(raw_label)
            if nk not in CANONICAL_KEYS:
                continue
            value = _to_canonical_value(nk, val, _unit_from_label(raw_label))
            metrics[nk] = {
                "median": value,
                "displayName": CANONICAL_DISPLAY[nk],
                "unit": CANONICAL_UNIT[nk],
                "source": "xcodebuild_log",
            }
    return metrics


def extract_metrics(xcresult: Path, xcodebuild_log: Path | None) -> dict[str, Any]:
    root = load_xcresult_json(xcresult)
    blobs = _merge_blobs(root)

    metrics: dict[str, Any] = {}
    raw: list[dict[str, Any]] = []

    for blob in blobs:
        median, display, unit = _median_from_metric_blob(blob)
        raw.append({"display": display, "unit": unit, "median": median})
        nk = _normalize_key(display)
        if nk in CANONICAL_KEYS and median is not None:
            metrics[nk] = {
                "median": _to_canonical_value(nk, median, unit),
                "displayName": CANONICAL_DISPLAY[nk],
                "unit": CANONICAL_UNIT[nk],
                "source": "xcresult",
            }

    log_metrics: dict[str, Any] = {}
    if xcodebuild_log:
        log_metrics = parse_xcodebuild_log(xcodebuild_log)
        for key, entry in log_metrics.items():
            if key not in metrics:
                metrics[key] = entry
            elif metrics[key].get("median") is None and entry.get("median") is not None:
                metrics[key] = entry

    out: dict[str, Any] = {
        "schemaVersion": 1,
        "extractedAt": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "rawPerformanceObjects": len(blobs),
        "logMetricKeys": len(log_metrics),
    }
    if os.environ.get("PERF_DEBUG"):
        out["_debugRaw"] = raw[:80]
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--xcresult", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--xcodebuild-log",
        type=Path,
        default=None,
        help="Optional path to xcodebuild test stdout/stderr (tee) for measured-average fallback.",
    )
    args = p.parse_args()

    if not args.xcresult.exists():
        empty = {
            "schemaVersion": 1,
            "extractedAt": datetime.now(timezone.utc).isoformat(),
            "metrics": {},
            "rawPerformanceObjects": 0,
            "logMetricKeys": 0,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(empty, indent=2), encoding="utf-8")
        print(f"Wrote empty metrics to {args.out} (no xcresult)")
        return

    doc = extract_metrics(args.xcresult, args.xcodebuild_log)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    n = len(doc.get("metrics") or {})
    print(f"Wrote {args.out} (metrics: {n}, blobs: {doc.get('rawPerformanceObjects')}, logKeys: {doc.get('logMetricKeys')})")


if __name__ == "__main__":
    main()
