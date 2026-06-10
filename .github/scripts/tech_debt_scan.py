#!/usr/bin/env python3
"""Scan TS/JS sources under src/ for tech-debt markers."""
from __future__ import annotations
import re, sys
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Finding:
    priority: str
    tag: str
    path: str
    line_no: int
    line: str

PATTERNS = [
    (re.compile(r"\bTECHDEBT\s*(\([^)]*\))?\s*:", re.I), "P1", "TECHDEBT"),
    (re.compile(r"\bFIXME\b"), "P1", "FIXME"),
    (re.compile(r"\bHACK\b"), "P1", "HACK"),
    (re.compile(r"\bXXX\b"), "P2", "XXX"),
    (re.compile(r"\bTODO\b"), "P2", "TODO"),
    (re.compile(r"\bOPTIMIZE\b"), "P3", "OPTIMIZE"),
    (re.compile(r"\bREFACTOR\b"), "P3", "REFACTOR"),
]
SKIP = {"node_modules", ".git", "build", ".expo", "Pods", "DerivedData"}

def skip_path(p: Path, root: Path) -> bool:
    try:
        rel = p.relative_to(root)
    except ValueError:
        return True
    return any(x in SKIP for x in rel.parts)

def main() -> int:
    root = Path.cwd()
    (root / "Reports").mkdir(parents=True, exist_ok=True)
    out = root / "Reports" / "tech-debt.md"
    files = sorted([p for p in (root / "src").rglob("*") if p.suffix in {".ts", ".tsx", ".js", ".jsx"} and p.is_file() and not skip_path(p, root)])
    findings = []
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            for pat, pr, tag in PATTERNS:
                if pat.search(line):
                    findings.append(Finding(pr, tag, str(fp.relative_to(root)), i, line.strip()[:200]))
                    break
    lines = ["# Tech debt scan", "", f"Files scanned: **{len(files)}**", f"Markers: **{len(findings)}**", ""]
    if not findings:
        lines.append("_No markers._")
    else:
        lines += ["| P | Tag | Loc | Snippet |", "|---|-----|-----|---------|"]
        for f in findings:
            lines.append(f"| {f.priority} | {f.tag} | `{f.path}:{f.line_no}` | {f.line.replace('|', chr(92)+'|')} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    return 0
if __name__ == "__main__":
    sys.exit(main())
