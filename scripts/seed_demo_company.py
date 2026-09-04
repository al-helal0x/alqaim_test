#!/usr/bin/env python3
"""seed_demo_company.py — إنشاء شركة/فرع/مستودع تجريبي كامل لبيئة التطوير.

مهمة #2 (خطة جولة الإغلاق — مسار 🔧 Infra) — انظر
`AlQaim_V2_خطة_20_مهمة.md` بند 2 و`scripts/README.md`.

يعيد استخدام Use Cases الحقيقية من apps/core-api بدل تكرار منطق الإدراج
(RegisterCompanyUseCase / CreateBranchUseCase / CreateWarehouseUseCase /
Catalog use cases) — بنفس القواعد التي يمر بها أي تسجيل حقيقي عبر الـ API
(دور Owner + كل الصلاحيات، تجزئة كلمة المرور، إلخ)، بدل إدراج صفوف SQL خام.

الاستخدام:
    cd apps/core-api && pip install -e . --break-system-packages   # أول مرة فقط
    python ../../scripts/seed_demo_company.py
    python ../../scripts/seed_demo_company.py --reset      # حذف الشركة التجريبية وإعادة زرعها
    python ../../scripts/seed_demo_company.py --company-name "شركة أخرى" --admin-email owner@x.com

يتطلب قاعدة بيانات core-api متاحة وهجرات مطبَّقة مسبقاً (`run_migrations.sh`).
يقرأ رابط الاتصال من نفس متغيرات البيئة التي يقرأها التطبيق
(`ALQAIM_DATABASE_URL` أو `.env` داخل apps/core-api)، وليس من قيم مكرَّرة هنا.
قابل لإعادة التشغيل بأمان (idempotent): إن كانت الشركة موجودة مسبقاً بنفس
الاسم لا يُعاد إنشاؤها، ما لم يُمرَّر `--reset`.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# السكربت يعيش في scripts/ على جذر المستودع، لكن كل الكود (modules/,
# platform_core/, shared_kernel/) موجود داخل apps/core-api — لا حزمة مثبَّتة
# باسم عام نعتمد عليها، فنضيف المسار صراحة بدل افتراض أن المستخدم شغّل
# السكربت من داخل apps/core-api يدوياً.
_CORE_API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "core-api"
if str(_CORE_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_API_ROOT))

try:
    from sqlalchemy import select
except ModuleNotFoundError as exc:  # pragma: no cover - رسالة تشخيص فقط
    print(
        "خطأ: حزم core-api غير مثبَّتة في بيئة بايثون الحالية.\n"
        "شغّل أولاً: cd apps/core-api && pip install -e '.[dev]' --break-system-packages",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_demo_company")

DEFAULT_COMPANY_NAME = "شركة القائم التجريبية"
DEFAULT_ADMIN_EMAIL = "admin@demo.alqaim.io"  # ليس .local/.test/.example: مرفوضة كنطاقات محجوزة من pydantic EmailStr
DEFAULT_ADMIN_PASSWORD = "ChangeMe123!"  # noqa: S105 — بيانات بيئة تطوير محلية فقط، ليست سرّاً إنتاجياً
DEFAULT_ADMIN_NAME = "مدير النظام التجريبي"
DEFAULT_BRANCH_NAME = "الفرع الرئيسي"
DEFAULT_WAREHOUSE_NAME = "المستودع الرئيسي"


async def _seed(args: argparse.Namespace) -> None:
    # الاستيراد داخل الدالة (وليس أعلى الملف) عمداً: sys.path يُعدَّل أعلاه
    # قبل أول استيراد لأي شيء من modules/platform_core، ولضمان ظهور رسالة
    # الخطأ الواضحة أعلاه بدل ImportError مبهم لو لم تُثبَّت الحزم بعد.
    from modules.catalog.application.dto.catalog_dto import (
        CategoryCreateRequest,
        PriceListCreateRequest,
        PriceListItemCreateRequest,
        ProductCreateRequest,
        UomCreateRequest,
    )
    from modules.catalog.application.use_cases.catalog_use_cases import (
        CreateCategoryUseCase,
        CreateUomUseCase,
    )
    from modules.catalog.infrastructure.models.catalog_models import Product
    from modules.identity.application.dto.identity_dto import RegisterCompanyRequest
    from modules.identity.application.use_cases.auth_use_cases import (
        OWNER_ROLE_CODE,
        RegisterCompanyUseCase,
    )
    from modules.identity.infrastructure.models.identity_models import Role, UserCompanyRole
    from modules.identity.infrastructure.repositories.user_repository import UserRepository
    from modules.tenancy.application.dto.tenancy_dto import (
        BranchCreateRequest,
        WarehouseCreateRequest,
    )
    from modules.tenancy.application.use_cases.company_use_cases import (
        CreateBranchUseCase,
        CreateWarehouseUseCase,
    )
    from modules.tenancy.infrastructure.models.tenancy_models import Company
    from platform_core.auth_middleware import TenantContext
    from platform_core.config import get_settings
    from platform_core.database import AsyncSessionLocal, engine

    settings = get_settings()
    log.info("قاعدة البيانات المستهدَفة: %s", _mask_password(settings.database_url))

    async with AsyncSessionLocal() as session:
        existing_stmt = select(Company).where(Company.name == args.company_name)
        existing_company = (await session.execute(existing_stmt)).scalar_one_or_none()

        if existing_company is not None and args.reset:
            log.info("--reset: حذف الشركة التجريبية الموجودة (%s) وإعادة زرعها…", existing_company.id)
            # حذف فعلي (وليس soft-delete) — بيانات تجريبية فقط، بترتيب يحترم
            # المفاتيح الأجنبية: الأبناء أولاً ثم الشركة نفسها.
            await _hard_delete_company_tree(session, existing_company.id)
            existing_company = None

        if existing_company is not None:
            log.info(
                "الشركة '%s' موجودة مسبقاً (id=%s) — لا شيء لفعله. استخدم --reset لإعادة الزرع.",
                args.company_name,
                existing_company.id,
            )
            await _print_login_hint(session, args.company_name, args.admin_email)
            return

        # 1) الشركة + دور Owner (بكل الصلاحيات) + المستخدم الإداري — عبر نفس
        #    مسار onboarding الحقيقي (Bootstrap) المستخدَم من /auth/register.
        register_use_case = RegisterCompanyUseCase(session)
        await register_use_case.execute(
            RegisterCompanyRequest(
                company_name=args.company_name,
                default_currency=args.currency,
                admin_full_name=args.admin_name,
                admin_email=args.admin_email,
                admin_password=args.admin_password,
            )
        )

        company = (
            await session.execute(select(Company).where(Company.name == args.company_name))
        ).scalar_one()
        owner_role = (
            await session.execute(
                select(Role).where(Role.company_id == company.id, Role.code == OWNER_ROLE_CODE)
            )
        ).scalar_one()
        admin_user = await UserRepository(session).get_by_email(args.admin_email)
        ctx = TenantContext(company_id=str(company.id), user_id=str(admin_user.id))

        # 2) الفرع + المستودع (Use Cases الحقيقية — تلتزم بنفس التحقق المستخدَم
        #    خلف /branches و/warehouses، بما فيها التأكد أن المستودع يعود لفرع
        #    قائم فعلاً بنفس الشركة).
        branch = await CreateBranchUseCase(session).execute(
            ctx, BranchCreateRequest(name=args.branch_name)
        )
        warehouse = await CreateWarehouseUseCase(session).execute(
            ctx, WarehouseCreateRequest(branch_id=str(branch.id), name=args.warehouse_name)
        )

        # 3) بيانات كتالوج تجريبية بسيطة (تصنيف + وحدة قياس + منتج + قائمة
        #    أسعار افتراضية) — مفيدة فعلياً لأي عضو يجرّب Sales/POS/Purchasing
        #    محلياً دون الحاجة لإنشائها يدوياً في كل مرة.
        category = await CreateCategoryUseCase(session).execute(
            ctx, CategoryCreateRequest(name="عام")
        )
        uom = await CreateUomUseCase(session).execute(
            ctx, UomCreateRequest(code="PCS", name="قطعة")
        )

        product = Product(
            company_id=company.id,
            sku="DEMO-0001",
            name="منتج تجريبي",
            category_id=category.id,
            base_uom_id=uom.id,
            sale_price=10000,
            purchase_price=7000,
        )
        session.add(product)
        await session.flush()

        price_list = None
        # PriceList/PriceListItem use cases غير مضافة بعد في catalog_use_cases —
        # إدراج مباشر هنا (نفس نمط RegisterCompanyUseCase أعلاه، لا واجهة API له بعد).
        from modules.catalog.infrastructure.models.catalog_models import PriceList, PriceListItem

        price_list = PriceList(
            company_id=company.id, name="قائمة الأسعار الافتراضية", currency=args.currency,
            is_default=True,
        )
        session.add(price_list)
        await session.flush()
        session.add(
            PriceListItem(price_list_id=price_list.id, product_id=product.id, price=10000)
        )

        await session.commit()

        log.info("تم إنشاء الشركة التجريبية بنجاح:")
        log.info("  الشركة:    %s (id=%s)", company.name, company.id)
        log.info("  الفرع:     %s (id=%s)", branch.name, branch.id)
        log.info("  المستودع:  %s (id=%s)", warehouse.name, warehouse.id)
        log.info("  المنتج:    %s / %s", product.sku, product.name)
        await _print_login_hint(session, args.company_name, args.admin_email, args.admin_password)

    await engine.dispose()


async def _hard_delete_company_tree(session, company_id) -> None:
    """حذف فعلي لكل صفوف الشركة التجريبية عند --reset، بترتيب يحترم FKs.

    محدود عمداً للجداول التي يزرعها هذا السكربت فقط (Company/Branch/Warehouse/
    Identity/Catalog) — ليس أداة حذف شركة عامة؛ لو أُضيفت بيانات أخرى يدوياً
    (فواتير، قيود محاسبية...) على نفس الشركة التجريبية، هذا الحذف سيفشل بخطأ
    FK بدل حذف صامت جزئي، وهذا هو السلوك المطلوب (لا حذف بيانات لم يُنشئها).
    """
    from sqlalchemy import delete

    from modules.catalog.infrastructure.models.catalog_models import (
        PriceList,
        PriceListItem,
        Product,
        ProductCategory,
        UnitOfMeasure,
    )
    from modules.identity.infrastructure.models.identity_models import (
        Role,
        RolePermission,
        User,
        UserCompanyRole,
    )
    from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse

    role_ids_subq = select(Role.id).where(Role.company_id == company_id)
    price_list_ids_subq = select(PriceList.id).where(PriceList.company_id == company_id)

    # نجمع مستخدمي هذه الشركة *قبل* حذف عضوياتهم (UserCompanyRole) — لازم
    # لتقرير أدناه من يمكن حذفه فعلياً (من لم يعد له أي عضوية شركة متبقية)
    # بدل حذف كل مستخدم مرتبط بالشركة التجريبية دون تمييز (قد يكون نفس
    # البريد استُخدم يدوياً للانضمام لشركة أخرى بعد الزرع الأول).
    user_ids_of_company = (
        (
            await session.execute(
                select(UserCompanyRole.user_id).where(UserCompanyRole.company_id == company_id)
            )
        )
        .scalars()
        .all()
    )

    await session.execute(
        delete(PriceListItem).where(PriceListItem.price_list_id.in_(price_list_ids_subq))
    )
    await session.execute(delete(PriceList).where(PriceList.company_id == company_id))
    await session.execute(delete(Product).where(Product.company_id == company_id))
    await session.execute(delete(UnitOfMeasure).where(UnitOfMeasure.company_id == company_id))
    await session.execute(delete(ProductCategory).where(ProductCategory.company_id == company_id))
    await session.execute(
        delete(RolePermission).where(RolePermission.role_id.in_(role_ids_subq))
    )
    await session.execute(delete(UserCompanyRole).where(UserCompanyRole.company_id == company_id))
    await session.execute(delete(Role).where(Role.company_id == company_id))
    await session.execute(delete(Warehouse).where(Warehouse.company_id == company_id))
    await session.execute(delete(Branch).where(Branch.company_id == company_id))
    await session.execute(delete(Company).where(Company.id == company_id))

    # الآن نحذف فقط المستخدمين الذين أصبحوا بلا أي عضوية شركة متبقية (أي أن
    # الشركة التجريبية كانت الوحيدة التي تخصهم) — وإلا فسيبقى --reset يفشل
    # لاحقاً بـ "البريد مستخدَم مسبقاً" رغم أن الشركة نفسها حُذفت فعلياً.
    for user_id in user_ids_of_company:
        remaining = (
            await session.execute(
                select(UserCompanyRole.id).where(UserCompanyRole.user_id == user_id)
            )
        ).scalar_one_or_none()
        if remaining is None:
            await session.execute(delete(User).where(User.id == user_id))

    await session.commit()


async def _print_login_hint(session, company_name: str, admin_email: str, admin_password: str | None = None) -> None:
    log.info("")
    log.info("لتسجيل الدخول عبر core-api:")
    log.info("  POST /auth/login  {\"email\": \"%s\", \"password\": \"%s\"}", admin_email, admin_password or "<كلمة المرور المستخدَمة عند الإنشاء الأول>")
    log.info("  الشركة: %s", company_name)


def _mask_password(database_url: str) -> str:
    if "@" not in database_url or "//" not in database_url:
        return database_url
    scheme_and_creds, rest = database_url.split("@", 1)
    scheme, _, _creds = scheme_and_creds.partition("//")
    return f"{scheme}//***:***@{rest}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company-name", default=DEFAULT_COMPANY_NAME, help="اسم الشركة التجريبية")
    parser.add_argument("--branch-name", default=DEFAULT_BRANCH_NAME, help="اسم الفرع")
    parser.add_argument("--warehouse-name", default=DEFAULT_WAREHOUSE_NAME, help="اسم المستودع")
    parser.add_argument("--currency", default="IQD", help="العملة الافتراضية للشركة")
    parser.add_argument("--admin-name", default=DEFAULT_ADMIN_NAME, help="اسم المستخدم الإداري")
    parser.add_argument("--admin-email", default=DEFAULT_ADMIN_EMAIL, help="بريد المستخدم الإداري")
    parser.add_argument("--admin-password", default=DEFAULT_ADMIN_PASSWORD, help="كلمة مرور المستخدم الإداري (8 أحرف على الأقل)")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="حذف الشركة التجريبية الموجودة بنفس الاسم (إن وُجدت) وإعادة زرعها من الصفر",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_seed(args))
    except Exception as exc:  # noqa: BLE001 — نريد رسالة واضحة للمستخدم النهائي، ليس traceback خام فقط
        log.error("فشل زرع الشركة التجريبية: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
