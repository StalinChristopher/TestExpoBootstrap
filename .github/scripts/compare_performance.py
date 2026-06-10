#!/usr/bin/env python3
"""
Compare current performance metrics JSON to baseline on main.

Baseline fallback strategy (mirrors Android perf_baselines.json pattern):
  1. Real baseline — ci/performance-baseline.json on main with non-empty metrics.
  2. Seed baseline  — ci/performance-seed.json with approximate values (checked in).
     Used automatically when the real baseline exists but has empty metrics (first
     real run on main has not captured live data yet, or extraction is still broken).
  3. No baseline   — first-time setup message shown; no comparison performed.

Exit code:
  - 0 by default (informational table + optional GitHub warnings).
  - 1 only when PERF_FAIL_ON_REGRESSION=true AND a *gated* metric regresses past threshold.

Simulator CI is noisy; failing every PR on any metric >12% is usually undesirable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _fmt_value(v: float | None) -> str:
    """Render a metric value with at most 3 decimals, trailing zeros stripped."""
    if v is None:
        return "—"
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s or "0"


def _median(entry: dict) -> float | None:
    if not isinstance(entry, dict):
        return None
    if "median" in entry:
        return float(entry["median"])
    return None


def format_delta(before: float | None, after: float | None) -> str:
    if before is None or after is None:
        return "—"
    delta = after - before
    if before == 0:
        return f"{delta:+.4f} (baseline 0 — pct n/a)"
    pct = (delta / before) * 100.0
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.4f} ({sign}{pct:.1f}%)"


def _label_for_row(key: str, b: dict | None, c: dict | None) -> str:
    if isinstance(c, dict) and c.get("displayName"):
        return str(c.get("displayName"))
    if isinstance(b, dict) and b.get("displayName"):
        return str(b.get("displayName"))
    return key


def _should_gate_failure(label_lower: str, gate_parts: list[str]) -> bool:
    if not gate_parts:
        return True
    return any(p in label_lower for p in gate_parts)


def _load_seed(seed_path: Path) -> dict:
    """Load seed metrics from ci/performance-seed.json.

    The seed schema stores metrics as objects with a 'median' key, matching the
    format expected by compare_performance — identical to a real baseline.
    """
    doc = json.loads(seed_path.read_text(encoding="utf-8"))
    return doc.get("metrics") if isinstance(doc.get("metrics"), dict) else {}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--current", required=True, type=Path)
    p.add_argument("--baseline", required=True, type=Path)
    p.add_argument(
        "--seed",
        type=Path,
        default=None,
        help="Seed baseline JSON (ci/performance-seed.json) used when baseline metrics are empty.",
    )
    p.add_argument("--threshold", type=float, default=float(os.environ.get("PERF_REGRESSION_THRESHOLD", "0.12")))
    p.add_argument("--summary-out", dest="summary_out", type=Path, default=None)
    args = p.parse_args()

    threshold: float = args.threshold

    fail_on = os.environ.get("PERF_FAIL_ON_REGRESSION", "false").strip().lower() in ("1", "true", "yes")
    gate_raw = os.environ.get("PERF_REGRESSION_GATE_SUBSTRINGS", "applaunch")
    gate_parts = [s.strip().lower() for s in gate_raw.split(",") if s.strip()]

    cur = json.loads(args.current.read_text(encoding="utf-8"))
    baseline_file_missing = not args.baseline.exists()
    base_doc = json.loads(args.baseline.read_text(encoding="utf-8")) if not baseline_file_missing else {}

    cur_metrics: dict = cur.get("metrics") if isinstance(cur.get("metrics"), dict) else {}
    base_metrics: dict = base_doc.get("metrics") if isinstance(base_doc.get("metrics"), dict) else {}

    baseline_has_record = bool(base_doc.get("gitSha") or base_doc.get("updatedAt"))
    base_populated = len(base_metrics) > 0

    # Seed fallback: when baseline exists on main but has no metric values yet,
    # substitute seed approximate values so PRs get a meaningful comparison
    # (mirrors Android's perf_baselines.json seed strategy).
    using_seed = False
    seed_tolerance: float | None = None
    if baseline_has_record and not base_populated and args.seed and args.seed.exists():
        seed_metrics = _load_seed(args.seed)
        if seed_metrics:
            base_metrics = seed_metrics
            base_populated = True
            using_seed = True
            try:
                seed_doc = json.loads(args.seed.read_text(encoding="utf-8"))
                tol = seed_doc.get("relativeTolerance")
                if isinstance(tol, (int, float)):
                    seed_tolerance = float(tol)
            except Exception:
                pass

    effective_threshold = seed_tolerance if (using_seed and seed_tolerance is not None) else threshold

    header = "| Metric | Baseline | PR | Δ | Status |"
    separator = "| --- | --- | --- | --- | --- |"

    lines: list[str] = []
    lines.append("### Performance vs baseline (`main`)\n")
    lines.append("")

    failed = False
    all_keys = sorted(set(cur_metrics.keys()) | set(base_metrics.keys()))

    if baseline_file_missing or (not baseline_has_record and not base_populated):
        lines.append(header)
        lines.append(separator)
        lines.append("| — | *no baseline yet* | — | — | ℹ️ |")
        lines.append("")
        lines.append(
            "**First-time setup:** `ci/performance-baseline.json` is missing or empty on `main`.\n\n"
            "Merge to `main` or run **Actions → Performance baseline (main)** to record a baseline."
        )
    elif baseline_has_record and not base_populated and not using_seed:
        lines.append(header)
        lines.append(separator)
        lines.append("| — | *baseline exists but metrics empty* | — | — | ⚹ |")
        lines.append("")
        lines.append(
            "Baseline file on `main` has no metric values yet (extraction issue). PR metrics below are informational."
        )
        for key in sorted(cur_metrics.keys()):
            c = cur_metrics.get(key)
            cm = _median(c) if isinstance(c, dict) else None
            label = _label_for_row(key, None, c if isinstance(c, dict) else None)
            lines.append(f"| {label} | — | {_fmt_value(cm)} | — | PR only |")
    else:
        # Seed note (if any) precedes the single results table.
        if using_seed:
            lines.append(
                f"> **Seed baseline** — real baseline on `main` has no metrics yet. "
                f"Comparing against approximate seed values from `ci/performance-seed.json` "
                f"(tolerance: {int(effective_threshold * 100)}%). "
                f"Once the **Performance baseline (main)** workflow records live data this note disappears."
            )
            lines.append("")

        lines.append(header)
        lines.append(separator)

        for key in all_keys:
            b = base_metrics.get(key)
            c = cur_metrics.get(key)
            bm = _median(b) if isinstance(b, dict) else None
            cm = _median(c) if isinstance(c, dict) else None
            label = _label_for_row(key, b if isinstance(b, dict) else None, c if isinstance(c, dict) else None)
            label_lower = label.lower()

            status = "—"
            if bm is not None and cm is not None:
                if bm == 0:
                    status = "✓ ok" if cm == 0 else "⚠️ noisy baseline"
                else:
                    rel = (cm - bm) / bm
                    if rel > effective_threshold:
                        status = "❌ regression"
                        gated = _should_gate_failure(label_lower, gate_parts)
                        if fail_on and gated:
                            failed = True
                            print(f"::error::Gated regression: {label} ↑ {rel * 100:.1f}% (threshold {effective_threshold * 100:.0f}%)")
                        elif fail_on and not gated:
                            status = "⚠️ above threshold (not gated)"
                            print(f"::notice::Non-gated drift: {label} ↑ {rel * 100:.1f}% — job still passes; tighten PERF_REGRESSION_GATE_SUBSTRINGS or threshold.")
                        else:
                            print(f"::warning::Regression (informational): {label} ↑ {rel * 100:.1f}% — job does not fail (set PERF_FAIL_ON_REGRESSION=true to enforce).")
                    elif rel < -effective_threshold:
                        status = "✅ improved"
                    else:
                        status = "✓ ok"
            elif cm is not None and bm is None:
                status = "new"
            elif bm is not None and cm is None:
                status = "⚠️ no PR data"

            lines.append(
                f"| {label} | {_fmt_value(bm)} | {_fmt_value(cm)} "
                f"| {format_delta(bm, cm)} | {status} |"
            )

    lines.append("")
    seed_note = " (seed)" if using_seed else ""
    lines.append(
        f"_Threshold: **{effective_threshold * 100:.0f}%**{seed_note} relative increase. "
        f"**Fail job on regression:** `PERF_FAIL_ON_REGRESSION`={str(fail_on).lower()}; "
        f"**Only count metrics whose label contains:** {gate_raw!r} (comma substrings, case-insensitive)._"
    )

    report = "\n".join(lines)
    print(report)

    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(report, encoding="utf-8")

    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        Path(gh_summary).open("a", encoding="utf-8").write("\n" + report + "\n")

    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
