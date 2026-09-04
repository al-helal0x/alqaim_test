"""Outbox Pattern — تنفيذ #6×#11×#12×#10، Track 1.

Outbox ≠ EventBus (القرار الحاسم في INTERFACE_CONTRACT_OUTBOX.md، تفعيل
فعلي لـ ADR-001 القرار 1): بعد Task #6-S1، `EventBus.publish(event_name,
payload)` صار نشراً فورياً في-الذاكرة فقط، بلا `session`، وبلا أي ضمان بقاء.
هذا الملف منفصل تماماً — `enqueue_event()` هو نقطة الدخول الوحيدة لأي use
case يريد نشر حدث "مضموناً" (لا يُفقَد حتى لو انهارت العملية مباشرة بعد
commit() وقبل وصول النشر الفعلي لأي مشترك): يكتب صفاً `pending` في جدول
`outbox_events` ضمن نفس معاملة قاعدة البيانات، الـ Worker المنفصل
(`outbox_worker.py`) يستطلع الصفوف الـ pending لاحقاً ويستدعي
`EventBus.publish()` الفعلي، ثم يعلّم الصف `dispatched`.

⚠️ توقيع `enqueue_event()` مجمَّد صراحة في INTERFACE_CONTRACT_OUTBOX.md —
لا يتغيّر بدون الرجوع لصاحب القرار (Track 2 وTrack 3 يبنيان ضده مباشرة).
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.outbox_models import OutboxEvent


async def enqueue_event(
    session: AsyncSession,
    *,
    event_name: str,
    payload: dict,
    aggregate_id: str,
) -> None:
    """يكتب صفاً `pending` في `outbox_events` ضمن معاملة `session` الحالية —
    **لا يستدعي `commit()`** (هذه مسؤولية المستدعي، كجزء من وحدة عمله
    الطبيعية: إما يُحفَظ التغيير التجاري + الحدث معاً ذرّياً، أو لا شيء
    منهما). لا يُنشر الحدث فوراً — `outbox_worker.py` هو من يتولى النشر
    الفعلي لاحقاً عبر `EventBus.publish()`، بشكل غير متزامن تماماً عن هذا
    الاستدعاء.
    """
    session.add(
        OutboxEvent(
            id=uuid.uuid4(),
            event_name=event_name,
            payload=payload,
            aggregate_id=aggregate_id,
            status="pending",
            attempts=0,
        )
    )
