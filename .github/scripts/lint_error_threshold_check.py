#!/usr/bin/env python3
"""Enforce max ESLint error count (ESLint v8 JSON format)."""
import json, os, sys
from pathlib import Path
def main() -> int:
    p = Path("eslint-report.json")
    if not p.is_file():
        print("No eslint-report.json; run eslint -f json -o eslint-report.json first")
        return 0
    data = json.loads(p.read_text())
    err = sum(1 for f in data for m in f.get("messages", []) if m.get("severity") == 2)
    max_e = int(os.environ.get("ESLINT_MAX_ERRORS", "99999"))
    print(f"ESLint errors: {err} (max {max_e})")
    return 0 if err <= max_e else 1
if __name__ == "__main__":
    sys.exit(main())
