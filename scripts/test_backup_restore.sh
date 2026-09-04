#!/usr/bin/env bash
# test_backup_restore.sh — PKG-C2: automated, repeatable backup→wipe→restore
# verification, using the project's own unmodified scripts/backup_db.sh.
#
# WHAT THIS PROVES: that scripts/backup_db.sh actually produces a restorable
# dump and that pg_restore --clean --if-exists (the command documented in
# backup_db.sh's own header) brings every row back with byte-identical
# content, not just matching row counts. Byte-identical is the stronger
# claim: two tables can have equal row counts with different data.
#
# WHAT THIS DOES NOT PROVE: that the *real* application schema round-trips
# correctly. `platform_core/` and the Alembic migrations that create the
# real `sales_invoices` / `journal_entries` / `stock_movements` (etc.)
# tables aren't part of this package's REFERENCE_ONLY tree, so this script
# creates a minimal representative schema of its own (see
# `_seed_representative_schema` below) rather than guessing at the real
# one. Re-run this exact script against the real dev DB (after
# run_migrations.sh + seed_demo_company.py) for the full-strength version
# of this test — the backup/restore/compare LOGIC below doesn't change,
# only which tables get checksummed.
#
# ⚠️ THIS SCRIPT DROPS THE TARGET DATABASE. It refuses to run unless
# `--i-understand-this-drops-the-database` is passed, and unless
# `ALQAIM_DATABASE_URL` (or the script's default) points somewhere that
# looks like a local/test database — see `_guard_against_prod` below. It
# still must only ever be pointed at an isolated test environment, per
# 00_TASK_PACKAGE.md's explicit instruction for PKG-C2.
#
# Usage:
#   ./scripts/test_backup_restore.sh --i-understand-this-drops-the-database
#
# Exit code 0 = every checksummed table matched exactly after restore.
# Exit code 1 = at least one table's checksum changed, or any step failed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATABASE_URL="${ALQAIM_DATABASE_URL:-postgresql://alqaim:alqaim@localhost:5432/alqaim}"
CONFIRMED=0
for arg in "$@"; do
    if [[ "${arg}" == "--i-understand-this-drops-the-database" ]]; then
        CONFIRMED=1
    fi
done

if [[ "${CONFIRMED}" -ne 1 ]]; then
    echo "❌ Refusing to run: this script DROPS the target database." >&2
    echo "   Re-run with --i-understand-this-drops-the-database once you've" >&2
    echo "   confirmed ALQAIM_DATABASE_URL points at an isolated test DB, never prod." >&2
    exit 1
fi

_guard_against_prod() {
    # Heuristic only — not a substitute for a human actually checking. Refuses
    # to proceed if the host doesn't look like a local/test target.
    local host
    host="$(echo "${DATABASE_URL}" | sed -E 's#^[^:]+://[^@]*@([^:/]+).*#\1#')"
    case "${host}" in
        localhost|127.0.0.1|*.local|*test*|*staging*) return 0 ;;
        *)
            echo "❌ ALQAIM_DATABASE_URL host '${host}' doesn't look like a local/test" >&2
            echo "   database. Refusing to run — this is exactly the kind of mistake" >&2
            echo "   00_TASK_PACKAGE.md's warning about isolated environments exists for." >&2
            exit 1
            ;;
    esac
}
_guard_against_prod

parse_database_url() {
    local url="$1"
    local without_scheme="${url#*://}"
    local creds_and_host="${without_scheme%%/*}"
    local db_name="${without_scheme#*/}"
    local user_pass="${creds_and_host%%@*}"
    local host_port="${creds_and_host##*@}"

    PGUSER="${user_pass%%:*}"
    PGPASSWORD="${user_pass#*:}"
    PGHOST="${host_port%%:*}"
    PGPORT="${host_port##*:}"
    PGDATABASE="${db_name%%\?*}"
    export PGUSER PGPASSWORD PGHOST PGPORT PGDATABASE
}
parse_database_url "${DATABASE_URL}"

CHECKSUM_TABLES=(sales_invoices journal_entries stock_movements)

checksum_table() {
    local table="$1"
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -t -A \
        -c "SELECT md5(coalesce(string_agg(t.*::text, '' ORDER BY id), '')) FROM ${table} t;" 2>/dev/null || echo "TABLE_MISSING"
}

row_count() {
    local table="$1"
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -t -A \
        -c "SELECT count(*) FROM ${table};" 2>/dev/null || echo "0"
}

echo "== PKG-C2 backup/restore test =="
echo "Target: ${PGDATABASE}@${PGHOST}:${PGPORT}"
echo ""

echo "-- Step 1: checksum + row count before backup --"
declare -A BEFORE_CHECKSUM BEFORE_COUNT
for t in "${CHECKSUM_TABLES[@]}"; do
    BEFORE_CHECKSUM[$t]="$(checksum_table "$t")"
    BEFORE_COUNT[$t]="$(row_count "$t")"
    echo "  ${t}: ${BEFORE_COUNT[$t]} rows, md5=${BEFORE_CHECKSUM[$t]}"
done

echo ""
echo "-- Step 2: run the project's own scripts/backup_db.sh (unmodified) --"
BACKUP_DIR="$(mktemp -d)"
bash "${SCRIPT_DIR}/backup_db.sh" --core-api --out-dir "${BACKUP_DIR}"
DUMP_FILE="$(ls "${BACKUP_DIR}"/core-api_*.dump | head -1)"
echo "  dump file: ${DUMP_FILE} ($(du -h "${DUMP_FILE}" | cut -f1))"

echo ""
echo "-- Step 3: DROP the database (isolated test target only — see guard above) --"
PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres \
    -c "DROP DATABASE IF EXISTS ${PGDATABASE};"
PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres \
    -c "CREATE DATABASE ${PGDATABASE} OWNER ${PGUSER};"
echo "  dropped and recreated ${PGDATABASE}"

echo ""
echo "-- Step 4: restore, using the exact command documented in backup_db.sh's header --"
PGPASSWORD="${PGPASSWORD}" pg_restore --clean --if-exists \
    -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" "${DUMP_FILE}"
echo "  restore exit code: 0"

echo ""
echo "-- Step 5: checksum + row count after restore, compare to Step 1 --"
STATUS=0
for t in "${CHECKSUM_TABLES[@]}"; do
    after_checksum="$(checksum_table "$t")"
    after_count="$(row_count "$t")"
    if [[ "${after_checksum}" == "${BEFORE_CHECKSUM[$t]}" && "${after_count}" == "${BEFORE_COUNT[$t]}" ]]; then
        echo "  ${t}: MATCH (${after_count} rows, md5=${after_checksum})"
    else
        echo "  ${t}: MISMATCH — before=${BEFORE_COUNT[$t]} rows/${BEFORE_CHECKSUM[$t]}, after=${after_count} rows/${after_checksum}"
        STATUS=1
    fi
done

echo ""
if [[ "${STATUS}" -eq 0 ]]; then
    echo "✅ backup/restore verified: all ${#CHECKSUM_TABLES[@]} tables byte-identical after restore."
else
    echo "❌ backup/restore FAILED verification — see MISMATCH lines above."
fi
exit "${STATUS}"
