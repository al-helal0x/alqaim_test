import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.application.dto.catalog_dto import (
    ProductCreateRequest,
    ProductImportRowResult,
    ProductImportSummary,
    ProductResponse,
    ProductUpdateRequest,
)
from modules.catalog.application.use_cases.catalog_use_cases import (
    CreateProductUseCase,
    GetProductUseCase,
    ListProductsPageUseCase,
    ListProductsUseCase,
    UpdateProductUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()

_EXPORT_COLUMNS = ["sku", "name", "product_type", "sale_price", "purchase_price", "is_active"]


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("catalog.product.create"))],
)
async def create_product(
    request: ProductCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProductResponse:
    try:
        product = await CreateProductUseCase(session).execute(ctx, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ProductResponse.model_validate(product)


@router.get("", response_model=Page[ProductResponse])
async def list_products(
    search: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[ProductResponse]:
    """موحّد عبر كل الموارد (blueprint القسم 9.3): page/page_size/sort.
    مثال: GET /products?search=قلم&category_id=...&sort=-created_at&page=1&page_size=20
    """
    products, total = await ListProductsPageUseCase(session).execute(
        ctx, params, search=search, category_id=category_id
    )
    return Page(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/export")
async def export_products(
    format: str = Query(default="csv", pattern="^(csv)$"),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """GET /products/export?format=xlsx في المخطط (القسم 9.4) — هذا الإصدار الأول
    يدعم csv فقط (بلا اعتمادية openpyxl إضافية)؛ xlsx يُضاف لاحقاً بنفس العقد
    دون كسر هذا الـ endpoint. المخرج بترميز utf-8-sig ليفتح Excel العربية بشكل صحيح.
    """
    products = await ListProductsUseCase(session).execute(ctx)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_EXPORT_COLUMNS)
    writer.writeheader()
    for product in products:
        writer.writerow({col: getattr(product, col) for col in _EXPORT_COLUMNS})

    byte_buffer = io.BytesIO(buffer.getvalue().encode("utf-8-sig"))
    return StreamingResponse(
        byte_buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_export.csv"},
    )


@router.post(
    "/import",
    response_model=ProductImportSummary,
    dependencies=[Depends(require_permission("catalog.product.create"))],
)
async def import_products(
    file: UploadFile,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProductImportSummary:
    """POST /products/import (القسم 9.4). المخطط يطلب معالجة غير متزامنة عبر
    job_id + GET /imports/{job_id}/status — هذا يتطلب Job Queue (Celery) لم
    تُوصَل بعد لـ core-api في هذه المرحلة (skeleton). هذا الإصدار الأول يعالج
    الملف مزامنةً ويعيد نتيجة كل سطر مباشرة؛ يُستبدَل لاحقاً بمسار Job بلا كسر
    للعقد الحالي (يبقى /products/import، يتغيّر فقط شكل الاستجابة لـ job_id).
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ترميز الملف غير مدعوم — استخدم UTF-8"
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    results: list[ProductImportRowResult] = []
    succeeded = 0

    for row_number, row in enumerate(reader, start=2):  # الصف 1 هو الترويسة
        try:
            request = ProductCreateRequest(
                sku=row["sku"],
                name=row["name"],
                base_uom_id=row["base_uom_id"],
                sale_price=row.get("sale_price") or "0",
                purchase_price=row.get("purchase_price") or "0",
            )
            await CreateProductUseCase(session).execute(ctx, request)
            results.append(ProductImportRowResult(row_number=row_number, sku=row.get("sku", ""), success=True))
            succeeded += 1
        except (ValueError, KeyError) as exc:
            results.append(
                ProductImportRowResult(
                    row_number=row_number, sku=row.get("sku", ""), success=False, error=str(exc)
                )
            )

    return ProductImportSummary(
        total_rows=len(results), succeeded=succeeded, failed=len(results) - succeeded, rows=results
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProductResponse:
    try:
        product = await GetProductUseCase(session).execute(ctx, product_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ProductResponse.model_validate(product)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(require_permission("catalog.product.update"))],
)
async def update_product(
    product_id: str,
    request: ProductUpdateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProductResponse:
    try:
        product = await UpdateProductUseCase(session).execute(ctx, product_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ProductResponse.model_validate(product)


