#!/usr/bin/env bash
# generate_lint_baseline.sh — TASK-CI-04 tooling: regenerate known_failures.txt
# in the EXACT format apps/core-api/known_failures.txt and
# apps/ai-platform/known_failures.txt already use (established by TASK-CI-03,
# 2026-08-13) — raw `ruff check . --output-format=concise` lines, one
# violation per line, no aggregation.
#
# This intentionally does NOT introduce a different baseline format. An
# earlier version of this script (PKG-C session, before this repo's real
# known_failures.txt was visible) grouped by (file, rule_code, count)
# instead — that format is incompatible with the one already established
# here and would have thrown away real, already-verified baseline work
# (including the documented correction of the plan's stale "278" figure
# to the real 78). This version replaces that approach with the project's
# own convention instead of competing with it.
#
# ⚠️ Known limitation of exact-line matching (demonstrated for real while
# merging this): an unrelated one-line edit above an existing violation
# shifts its line number, which the exact-line format then reports as
# "violation disappeared + new violation appeared" even though nothing
# about that violation actually changed. Confirmed happening already in
# apps/core-api/known_failures.txt as of this session — see
# audit/PKG-C4_merge_report.md for the specific example (two E741 entries
# in tests/integration/test_period_closing.py shifted by exactly one line
# each). This is a real trade-off of the format already chosen here, not
# something this script can fix without changing that format — flagging
# it, not silently working around it.
#
# Usage (run from inside the app directory, matching the existing files'
# own documented generation command exactly):
#   cd apps/core-api    && ../../scripts/generate_lint_baseline.sh
#   cd apps/ai-platform && ../../scripts/generate_lint_baseline.sh
#
# Prints to stdout — redirect to known_failures.txt yourself after
# reviewing the diff against the current file, the same way you would
# review any other regeneration of committed, already-reviewed output.

set -euo pipefail

ruff check . --output-format=concise 2>/dev/null | \
    grep -E '^\S+:[0-9]+:[0-9]+: [A-Z]+[0-9]+' | \
    sort
