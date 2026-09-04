#!/usr/bin/env python3
"""check_lint_against_baseline.py — TASK-CI-04 tooling: fail only on lint
violations NOT present in the existing known_failures.txt (exact-line
format, as already established by apps/core-api/known_failures.txt and
apps/ai-platform/known_failures.txt — see those files' own header
comments for the full convention this script deliberately matches rather
than replaces).

Comparison is a plain set difference over whole ruff-concise output lines
(after stripping the baseline file's `#`-comment header). A line is "new"
if it's produced by `ruff check . --output-format=concise` right now but
is not byte-identical to any line already in known_failures.txt.

⚠️ Read this before wiring this into a blocking CI step: exact-line
comparison means a genuinely unrelated one-line edit above an existing
violation shifts its line number and makes it look "new" even though
nothing about that violation changed. This was independently confirmed
against this project's real, current known_failures.txt while building
this script (two entries in tests/integration/test_period_closing.py had
shifted by one line each versus the recorded baseline, from an unrelated
edit elsewhere in the file) — this is a real, already-observed source of
false positives with the format as currently defined, not a hypothetical
edge case. Regenerating the baseline (generate_lint_baseline.sh) absorbs
line-shift noise along with any genuinely new debt each time it's run,
which is the tool's only available lever against this given the existing
format — a real fix (e.g. matching on rule+message ignoring line number)
would change the established convention and wasn't done here for that
reason.

Usage:
    python3 check_lint_against_baseline.py known_failures.txt

Exit 0: every current violation is already recorded in the baseline.
Exit 1: at least one violation isn't — prints exactly which, and why.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

VIOLATION_LINE_RE = re.compile(r"^\S+:[0-9]+:[0-9]+: [A-Z]+[0-9]+")


def parse_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        if VIOLATION_LINE_RE.match(raw):
            lines.add(raw)
    return lines


def current_violations() -> list[str]:
    result = subprocess.run(
        ["ruff", "check", ".", "--output-format=concise"],
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if VIOLATION_LINE_RE.match(line)]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_lint_against_baseline.py known_failures.txt", file=sys.stderr)
        return 2

    baseline_path = Path(sys.argv[1])
    baseline = parse_baseline(baseline_path)
    current = current_violations()

    new_lines = [line for line in current if line not in baseline]

    if not new_lines:
        print(f"✅ No violations outside {baseline_path} ({len(current)} current, all in baseline).")
        return 0

    print(f"❌ {len(new_lines)} violation(s) not in {baseline_path}:\n")
    for line in new_lines:
        print(f"  {line}")
    print(
        "\nIf this is inherited debt from other merged work (not something you just "
        "introduced) — e.g. a file this baseline predates — regenerate the baseline "
        "with generate_lint_baseline.sh and review the diff before committing it. "
        "Note: line-shift false positives are possible here — see this script's "
        "own docstring — so check whether a reported line is genuinely new code "
        "before assuming it is."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
