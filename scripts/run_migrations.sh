#!/usr/bin/env bash
# run_migrations.sh — تشغيل Alembic على كل قواعد البيانات في المشروع.
#
# مهمة #2 (خطة جولة الإغلاق — مسار 🔧 Infra) — انظر
# AlQaim_V2_خطة_20_مهمة.md بند 2 وscripts/README.md.
#
# المشروع يحتوي قاعدتي بيانات منفصلتين تماماً (docs/architecture/contracts.md):
#   - core-api    → apps/core-api    (متغير البيئة ALQAIM_DATABASE_URL)
#   - ai-platform → apps/ai-platform (متغير البيئة ALQAIM_AI_DATABASE_URL)
# هذا السكربت يشغّل "alembic upgrade head" على الاثنتين بالتتابع.
#
# الاستخدام:
#   ./scripts/run_migrations.sh                 # الاثنتان (core-api ثم ai-platform)
#   ./scripts/run_migrations.sh core-api         # core-api فقط
#   ./scripts/run_migrations.sh ai-platform      # ai-platform فقط
#   ./scripts/run_migrations.sh --downgrade -1   # تمرَّر كما هي إلى alembic (بعد اسم الخدمة إن وُجد)
#
# لا يفرض رابط اتصال هنا: يقرأ Alembic نفسه الإعداد من نفس متغيرات البيئة
# التي يقرأها التطبيق (platform_core/config.py في كل خدمة عبر migrations/env.py)،
# فتصدير ALQAIM_DATABASE_URL / ALQAIM_AI_DATABASE_URL (أو .env محلي) كافٍ لتغيير
# الهدف دون تعديل هذا السكربت.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET="${1:-all}"
if [[ "${TARGET}" == "core-api" || "${TARGET}" == "ai-platform" ]]; then
    shift
fi
ALEMBIC_ARGS=("$@")
if [[ ${#ALEMBIC_ARGS[@]} -eq 0 ]]; then
    ALEMBIC_ARGS=(upgrade head)
fi

run_alembic_for() {
    local service_name="$1"
    local service_dir="${REPO_ROOT}/apps/${service_name}"

    if [[ ! -d "${service_dir}" ]]; then
        echo "⚠️  تخطّي ${service_name}: المجلد غير موجود (${service_dir})" >&2
        return 0
    fi
    if [[ ! -f "${service_dir}/alembic.ini" ]]; then
        echo "⚠️  تخطّي ${service_name}: alembic.ini غير موجود" >&2
        return 0
    fi
    if ! (cd "${service_dir}" && python3 -c "import alembic" 2>/dev/null); then
        echo "❌ ${service_name}: حزمة alembic غير مثبَّتة في بيئة بايثون الحالية." >&2
        echo "   شغّل أولاً: cd apps/${service_name} && pip install -e '.[dev]' --break-system-packages" >&2
        return 1
    fi

    echo "▶️  ${service_name}: alembic ${ALEMBIC_ARGS[*]}"
    # لا نعتمد على propagation التلقائي لـ `set -e` عبر استدعاء الدالة: هذه
    # الدالة تُستدعى دائماً ضمن قائمة `||` من المتصل (run_alembic_for ... ||
    # status=1)، و-e يُعطَّل ضمنياً داخل كامل سلسلة استدعاء كهذه في bash —
    # فنتحقق من رمز الخروج صراحةً بدل الاعتماد على أن فشل الأمر الداخلي يوقف
    # تنفيذ الدالة تلقائياً (وإلا ستُطبَع "تم بنجاح" حتى لو فشل alembic فعلياً).
    if (cd "${service_dir}" && python3 -m alembic "${ALEMBIC_ARGS[@]}"); then
        echo "✅ ${service_name}: تم بنجاح."
        return 0
    else
        echo "❌ ${service_name}: فشل alembic (راجع المخرجات أعلاه)." >&2
        return 1
    fi
}

status=0

if [[ "${TARGET}" == "all" || "${TARGET}" == "core-api" ]]; then
    run_alembic_for "core-api" || status=1
fi

if [[ "${TARGET}" == "all" || "${TARGET}" == "ai-platform" ]]; then
    # ملاحظة معروفة: قاعدة بيانات ai-platform (alqaim_ai على المنفذ 5433
    # افتراضياً — راجع apps/ai-platform/platform_core/config.py) غير مُعرَّفة
    # حالياً كخدمة في docker-compose.yml (خارج نطاق هذه المهمة #2 التي تقتصر
    # على scripts/) — إن لم تكن متاحة سيفشل الاتصال بوضوح بدل صمت، مع رسالة
    # تشرح السبب بدل traceback مبهم فقط.
    if ! run_alembic_for "ai-platform"; then
        echo "   تلميح: تأكد أن قاعدة بيانات ai-platform متاحة (راجع ALQAIM_AI_DATABASE_URL) —" >&2
        echo "   docker-compose.yml الحالي لا يشغّل Postgres منفصلاً لها بعد." >&2
        status=1
    fi
fi

exit "${status}"
