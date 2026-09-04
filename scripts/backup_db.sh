#!/usr/bin/env bash
# backup_db.sh — نسخ احتياطي يدوي محلي لقاعدة (قواعد) بيانات المشروع.
#
# مهمة #2 (خطة جولة الإغلاق — مسار 🔧 Infra) — انظر
# AlQaim_V2_خطة_20_مهمة.md بند 2 وscripts/README.md.
#
# ينسخ احتياطياً قاعدة core-api (alqaim) افتراضياً عبر pg_dump، بصيغة مضغوطة
# مناسبة لـ "pg_restore"، إلى مجلد محلي (لا يُرفَع لأي تخزين سحابي — نسخ
# احتياطي يدوي للتطوير المحلي فقط، وليس بديلاً عن استراتيجية نسخ احتياطي
# إنتاجية حقيقية).
#
# الاستخدام:
#   ./scripts/backup_db.sh                    # نسخ core-api فقط (الافتراضي)
#   ./scripts/backup_db.sh --all               # core-api + ai-platform (إن كانت متاحة)
#   ./scripts/backup_db.sh --ai-platform        # ai-platform فقط
#   ./scripts/backup_db.sh --out-dir /path      # مجلد وجهة مختلف (الافتراضي: var/backups/)
#
# يقرأ رابط الاتصال من نفس متغيرات البيئة التي يستخدمها التطبيق نفسه
# (ALQAIM_DATABASE_URL لـ core-api، ALQAIM_AI_DATABASE_URL لـ ai-platform)،
# مع نفس القيم الافتراضية الموجودة في docker-compose.yml إن لم تُصدَّر.
#
# الاستعادة لاحقاً:
#   pg_restore --clean --if-exists -d <رابط القاعدة> <ملف .dump>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUT_DIR="${REPO_ROOT}/var/backups"
DO_CORE_API=1
DO_AI_PLATFORM=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            DO_CORE_API=1
            DO_AI_PLATFORM=1
            shift
            ;;
        --ai-platform)
            DO_CORE_API=0
            DO_AI_PLATFORM=1
            shift
            ;;
        --core-api)
            DO_CORE_API=1
            DO_AI_PLATFORM=0
            shift
            ;;
        --out-dir)
            OUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "${BASH_SOURCE[0]}"
            exit 0
            ;;
        *)
            echo "خيار غير معروف: $1" >&2
            exit 1
            ;;
    esac
done

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "❌ pg_dump غير مثبَّت على هذا الجهاز (حزمة postgresql-client)." >&2
    exit 1
fi

mkdir -p "${OUT_DIR}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# يحوّل رابط SQLAlchemy Async (postgresql+asyncpg://user:pass@host:port/db)
# إلى مكوّنات PGHOST/PGPORT/... يفهمها pg_dump — نفس الرابط المستخدَم فعلياً
# من التطبيق بدل تكرار بيانات الاتصال بشكل منفصل قد ينحرف عن الحقيقي.
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

backup_one() {
    local label="$1"
    local database_url="$2"

    parse_database_url "${database_url}"
    local out_file="${OUT_DIR}/${label}_${PGDATABASE}_${TIMESTAMP}.dump"

    echo "▶️  ${label}: نسخ ${PGDATABASE}@${PGHOST}:${PGPORT} → ${out_file}"
    if ! pg_dump --format=custom --no-owner --no-privileges --file="${out_file}"; then
        echo "❌ ${label}: فشل pg_dump (تأكد أن القاعدة متاحة على ${PGHOST}:${PGPORT})." >&2
        rm -f "${out_file}"
        return 1
    fi

    local size
    size="$(du -h "${out_file}" | cut -f1)"
    echo "✅ ${label}: تم (${size})."
}

status=0

if [[ "${DO_CORE_API}" -eq 1 ]]; then
    CORE_API_DATABASE_URL="${ALQAIM_DATABASE_URL:-postgresql://alqaim:alqaim@localhost:5432/alqaim}"
    backup_one "core-api" "${CORE_API_DATABASE_URL}" || status=1
fi

if [[ "${DO_AI_PLATFORM}" -eq 1 ]]; then
    AI_PLATFORM_DATABASE_URL="${ALQAIM_AI_DATABASE_URL:-postgresql://alqaim_ai:alqaim_ai@localhost:5433/alqaim_ai}"
    backup_one "ai-platform" "${AI_PLATFORM_DATABASE_URL}" || status=1
fi

if [[ "${status}" -eq 0 ]]; then
    echo ""
    echo "النسخ الاحتياطية في: ${OUT_DIR}"
fi

exit "${status}"
