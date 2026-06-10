#!/usr/bin/env python3
"""Aggregate eslint JSON + tech-debt + security into one summary."""
from __future__ import annotations
import json, os, re, sys
from collections import Counter
from pathlib import Path

def main() -> int:
    root = Path.cwd()
    rep = root / "Reports"
    rep.mkdir(parents=True, exist_ok=True)
    out = rep / "codebase-health-summary.md"
    sl = rep / "eslint.json"
    sev = Counter()
    if sl.is_file():
        try:
            data = json.loads(sl.read_text())
            for item in data if isinstance(data, list) else []:
                if isinstance(item, dict) and "severity" in item:
                    sev[str(item["severity"]).lower()] += 1
        except (json.JSONDecodeError, OSError):
            pass
    sha = os.environ.get("GITHUB_SHA", "local")[:7]
    lines = [
        "# Codebase health",
        f"- ref: `{sha}`",
        "",
        "## ESLint (from eslint.json)",
        f"Errors: {sev.get(2,0)+sev.get('error',0)}  Warnings: {sev.get(1,0)+sev.get('warning',0)}",
        "",
        "See also tech-debt.md and security-findings.md in the artifact.",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    return 0
if __name__ == "__main__":
    sys.exit(main())
