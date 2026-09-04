"""ترقيم صفحات موحّد (Offset-based) عبر كل الموارد — blueprint القسم 9.3.

كل Module يستخدم `PageParams` كـ FastAPI dependency و`paginate()` لتطبيقها على
أي `select()` من SQLAlchemy، بدل أن يعيد كل عضو اختراع نفس منطق
page/page_size/sort لكل قائمة (products, partners, invoices...).

Cursor-based pagination (`after=`) للقوائم الضخمة (سجل الحركات/Audit Log) يُضاف
لاحقاً كخيار منفصل عند الحاجة الفعلية (القسم 9.3) — لا يُستبدَل به هذا الملف.
"""
from dataclasses import dataclass
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = 20
    sort: str | None = None  # e.g. "-created_at" أو "name"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str | None = Query(default=None, description="مثال: -created_at أو name"),
) -> PageParams:
    """FastAPI dependency: `params: PageParams = Depends(page_params)`."""
    return PageParams(page=page, page_size=page_size, sort=sort)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def apply_sort(stmt: Select, model, sort: str | None) -> Select:
    """يطبّق `sort=-field`/`sort=field` على أي select — يتجاهل الحقول غير الموجودة
    على الـ model بدل أن يفشل (دفاعي: لا يكسر القائمة بسبب اسم حقل خاطئ)."""
    if not sort:
        return stmt
    descending = sort.startswith("-")
    field_name = sort[1:] if descending else sort
    column = getattr(model, field_name, None)
    if column is None:
        return stmt
    return stmt.order_by(column.desc() if descending else column.asc())


async def paginate(session: AsyncSession, stmt: Select, model, params: PageParams) -> tuple[list, int]:
    """يُنفّذ استعلام العدّ + استعلام الصفحة المطلوبة، ويعيد (rows, total)."""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = apply_sort(stmt, model, params.sort)
    stmt = stmt.offset(params.offset).limit(params.page_size)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return rows, total
