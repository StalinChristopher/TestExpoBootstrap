#!/usr/bin/env python3
"""Heuristic security scan for JS/TS and AndroidManifest."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RULES = [
    ("P1", "Hardcoded secret (suspected)", re.compile(
        r'(?i)(api[_-]?key|secret|password|token|bearer)\s*[=:]\s*["\x27][^"\x27]{8,}["\x27]'
    )),
    ("P2", "http:// URL", re.compile(r"['\"]http://[^'\"]+['\"]")),
    ("P1", "ATS / cleartext (Android)", re.compile(
        r'android:usesCleartextTraffic\s*=\s*"true"', re.I
    )),
]


def main() -> int:
    root = Path.cwd()
    (root / "Reports").mkdir(parents=True, exist_ok=True)
    out = root / "Reports" / "security-findings.md"
    rows: list[tuple[str, str, str, str]] = []
    src = root / "src"
    if src.is_dir():
        for pat in (".ts", ".tsx", ".js"):
            for p in src.rglob(f"*{pat}"):
                if not p.is_file():
                    continue
                for i, line in enumerate(
                    p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    for pr, _cat, rx in RULES:
                        if rx.search(line):
                            rows.append(
                                (pr, _cat, f"{p.relative_to(root)}:{i}", line.strip()[:120])
                            )
    man = root / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    if man.is_file():
        t = man.read_text(encoding="utf-8", errors="replace")
        for pr, cat, rx in RULES:
            if rx.search(t):
                rows.append((pr, cat, str(man.relative_to(root)), "(file match)"))
    lines = ["# Security (heuristic)", "", f"Findings: **{len(rows)}**", ""]
    for pr, cat, loc, sn in rows:
        lines.append(f"- **{pr}** {cat} `{loc}` — {sn}")
    if not rows:
        lines.append("_No heuristic security patterns matched._")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
