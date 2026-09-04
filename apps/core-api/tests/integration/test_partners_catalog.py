"""اختبار تكامل يغطي معيار تسليم العضو 2 (Master Data — Partners & Catalog):
CRUD أساسي، عزل الشركات، قيود التفرد (SKU/tax_number لكل شركة)، وأن الـ Ports
المعلَنة (IPartnerLookup/IProductLookup) تعيد None عبر حدود الشركات وليس بيانات
شركة أخرى.
"""
import uuid

import pytest

from modules.catalog.application.dto.catalog_dto import (
    CategoryCreateRequest,
    PriceListCreateRequest,
    PriceListItemCreateRequest,
    ProductCreateRequest,
    UomCreateRequest,
)
from modules.catalog.application.use_cases.catalog_use_cases import (
    AddPriceListItemUseCase,
    CreateCategoryUseCase,
    CreatePriceListUseCase,
    CreateProductUseCase,
    CreateUomUseCase,
)
from modules.catalog.infrastructure.repositories.product_lookup_repository import (
    SqlProductLookup,
)
from modules.partners.application.dto.partner_dto import PartnerCreateRequest
from modules.partners.application.use_cases.partner_use_cases import (
    CreatePartnerUseCase,
    DuplicateTaxNumberError,
    ListPartnersUseCase,
)
from modules.partners.domain.rules import PartnerType
from modules.partners.infrastructure.repositories.partner_lookup_repository import (
    SqlPartnerLookup,
)
from modules.tenancy.infrastructure.models.tenancy_models import Company
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


async def _make_company_ctx(db_session) -> TenantContext:
    company = Company(name=f"شركة {uuid.uuid4().hex[:8]}")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()))


# ── Partners ─────────────────────────────────────────────────────────────


async def test_create_and_list_partner(db_session):
    ctx = await _make_company_ctx(db_session)

    partner = await CreatePartnerUseCase(db_session).execute(
        ctx,
        PartnerCreateRequest(
            name="مؤسسة الفرات التجارية",
            partner_type=PartnerType.SUPPLIER,
            tax_number="TX-001",
        ),
    )
    assert partner.partner_type == "supplier"

    partners = await ListPartnersUseCase(db_session).execute(ctx)
    assert len(partners) == 1
    assert partners[0].name == "مؤسسة الفرات التجارية"


async def test_partner_lookup_respects_tenant_isolation(db_session):
    ctx_a = await _make_company_ctx(db_session)
    ctx_b = await _make_company_ctx(db_session)

    partner = await CreatePartnerUseCase(db_session).execute(
        ctx_a, PartnerCreateRequest(name="عميل شركة أ", partner_type=PartnerType.CUSTOMER)
    )

    lookup = SqlPartnerLookup(db_session)
    # نفس الشركة: يجب أن يعيد بيانات صحيحة
    found = await lookup.get(company_id=ctx_a.company_id, partner_id=str(partner.id))
    assert found is not None
    assert found.name == "عميل شركة أ"

    # شركة أخرى تحاول قراءة نفس partner_id: يجب أن تحصل على None وليس بيانات مسربة
    leaked = await lookup.get(company_id=ctx_b.company_id, partner_id=str(partner.id))
    assert leaked is None


async def test_duplicate_tax_number_raises_clear_error_not_500(db_session):
    """QA_FINDINGS_apps_web_manual_test.md #2: قبل الإصلاح، إنشاء مورد بنفس
    الرقم الضريبي لعميل موجود كان يُسقِط IntegrityError خاماً كـ500 غير
    معالَج (الراوتر لا يلتقط إلا ValueError). الآن يجب أن يُرفَع
    DuplicateTaxNumberError (وهو ValueError) برسالة عربية واضحة، والـsession
    يجب أن تبقى قابلة للاستخدام بعده (rollback فعلي، لا حالة معلَّقة)."""
    ctx = await _make_company_ctx(db_session)

    await CreatePartnerUseCase(db_session).execute(
        ctx,
        PartnerCreateRequest(name="شسيب", partner_type=PartnerType.CUSTOMER, tax_number="شسيب"),
    )

    with pytest.raises(DuplicateTaxNumberError):
        await CreatePartnerUseCase(db_session).execute(
            ctx,
            PartnerCreateRequest(
                name="شسيب للتوريد", partner_type=PartnerType.SUPPLIER, tax_number="شسيب"
            ),
        )

    # الـsession يجب أن تبقى صالحة بعد rollback الداخلي — تحقُّق فعلي بعملية
    # لاحقة ناجحة، لا افتراض.
    partners = await ListPartnersUseCase(db_session).execute(ctx)
    assert len(partners) == 1


async def test_credit_limit_cannot_be_negative(db_session):
    ctx = await _make_company_ctx(db_session)
    with pytest.raises(ValueError):
        await CreatePartnerUseCase(db_session).execute(
            ctx,
            PartnerCreateRequest(name="عميل غير صالح", credit_limit=-100),
        )


# ── Catalog ──────────────────────────────────────────────────────────────


async def _seed_uom_and_category(db_session, ctx: TenantContext):
    uom = await CreateUomUseCase(db_session).execute(
        ctx, UomCreateRequest(code="PCS", name="قطعة")
    )
    category = await CreateCategoryUseCase(db_session).execute(
        ctx, CategoryCreateRequest(name="مشروبات")
    )
    return uom, category


async def test_create_product_and_lookup_by_other_module(db_session):
    ctx = await _make_company_ctx(db_session)
    uom, category = await _seed_uom_and_category(db_session, ctx)

    product = await CreateProductUseCase(db_session).execute(
        ctx,
        ProductCreateRequest(
            sku="COLA-330",
            name="كولا 330 مل",
            category_id=str(category.id),
            base_uom_id=str(uom.id),
            sale_price="1500",
            purchase_price="1000",
        ),
    )

    # هذا بالضبط ما تستدعيه sales/inventory/purchasing عبر IProductLookup
    lookup = SqlProductLookup(db_session)
    dto = await lookup.get(company_id=ctx.company_id, product_id=str(product.id))
    assert dto is not None
    assert dto.sku == "COLA-330"
    assert dto.uom == "PCS"
    assert dto.is_active is True


async def test_duplicate_sku_within_same_company_rejected(db_session):
    ctx = await _make_company_ctx(db_session)
    uom, _ = await _seed_uom_and_category(db_session, ctx)

    await CreateProductUseCase(db_session).execute(
        ctx, ProductCreateRequest(sku="SKU-1", name="منتج 1", base_uom_id=str(uom.id))
    )
    with pytest.raises(ValueError, match="مستخدم بالفعل"):
        await CreateProductUseCase(db_session).execute(
            ctx, ProductCreateRequest(sku="SKU-1", name="منتج مكرر", base_uom_id=str(uom.id))
        )


async def test_same_sku_allowed_across_different_companies(db_session):
    ctx_a = await _make_company_ctx(db_session)
    ctx_b = await _make_company_ctx(db_session)
    uom_a, _ = await _seed_uom_and_category(db_session, ctx_a)
    uom_b, _ = await _seed_uom_and_category(db_session, ctx_b)

    # نفس الـ SKU في شركتين مختلفتين مسموح شرعاً (blueprint سطر 714)
    product_a = await CreateProductUseCase(db_session).execute(
        ctx_a, ProductCreateRequest(sku="SAME-SKU", name="منتج أ", base_uom_id=str(uom_a.id))
    )
    product_b = await CreateProductUseCase(db_session).execute(
        ctx_b, ProductCreateRequest(sku="SAME-SKU", name="منتج ب", base_uom_id=str(uom_b.id))
    )
    assert product_a.id != product_b.id


async def test_cannot_use_uom_from_another_company(db_session):
    ctx_a = await _make_company_ctx(db_session)
    ctx_b = await _make_company_ctx(db_session)
    uom_b, _ = await _seed_uom_and_category(db_session, ctx_b)

    with pytest.raises(ValueError, match="لا يعود لشركتك"):
        await CreateProductUseCase(db_session).execute(
            ctx_a,
            ProductCreateRequest(sku="X", name="منتج مخترق", base_uom_id=str(uom_b.id)),
        )


async def test_price_list_item_lifecycle(db_session):
    ctx = await _make_company_ctx(db_session)
    uom, _ = await _seed_uom_and_category(db_session, ctx)
    product = await CreateProductUseCase(db_session).execute(
        ctx, ProductCreateRequest(sku="P-1", name="منتج", base_uom_id=str(uom.id))
    )
    price_list = await CreatePriceListUseCase(db_session).execute(
        ctx, PriceListCreateRequest(name="جملة")
    )

    item = await AddPriceListItemUseCase(db_session).execute(
        ctx, str(price_list.id), PriceListItemCreateRequest(product_id=str(product.id), price="2000")
    )
    assert item.price == 2000

    # نفس المنتج مرتين في نفس قائمة الأسعار ممنوع
    with pytest.raises(ValueError, match="موجود بالفعل"):
        await AddPriceListItemUseCase(db_session).execute(
            ctx,
            str(price_list.id),
            PriceListItemCreateRequest(product_id=str(product.id), price="2100"),
        )
