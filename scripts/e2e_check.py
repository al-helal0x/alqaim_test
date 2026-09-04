#!/usr/bin/env python3
"""تحقق E2E حي واحد شامل — يُشغَّل من داخل حاوية core-api (يصل ai-platform
عبر البوابة الحقيقية على نفس شبكة docker). لا يعتمد على Pillow هنا عمداً
(غير مثبَّتة في core-api) — يقرأ صورة فاتورة مُولَّدة مسبقاً من
gen_invoice_image.py (شُغِّل داخل ai-platform التي تملك Pillow فعلاً)
بدل توليدها هنا مباشرة.

التسلسل الكامل المطلوب قبل هذا السكربت (بالترتيب):
    1) داخل ai-platform:  python /app/gen_invoice_image.py
    2) docker cp <ai-platform>:/app/invoice.png ./invoice.png   (من المضيف)
    3) docker cp ./invoice.png <core-api>:/app/invoice.png       (من المضيف)
    4) داخل core-api:      python /app/e2e_check.py

يقوم بما تبقّى تلقائياً:
  1. يسجّل الدخول بحساب المدير التجريبي للحصول على JWT صالح وقت التشغيل.
  2. يرفع /app/invoice.png عبر البوابة الحقيقية POST /ai/documents/analyze.
  3. يستطلع حالة job حتى status=done.
  4. يجلب المسودة النهائية ويطبع matched_supplier_id بوضوح.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

CORE_API = "http://localhost:8000"
ADMIN_EMAIL = "admin@demo.alqaim.io"
ADMIN_PASSWORD = "ChangeMe123!"
IMAGE_PATH = Path("/app/invoice.png")


def main() -> int:
    if not IMAGE_PATH.exists():
        print(
            f"❌ {IMAGE_PATH} غير موجود. شغّل أولاً gen_invoice_image.py داخل "
            "ai-platform ثم انسخ الملف الناتج إلى هنا (راجع تعليق أعلى الملف).",
            file=sys.stderr,
        )
        return 1
    image_bytes = IMAGE_PATH.read_bytes()

    with httpx.Client(base_url=CORE_API, timeout=30.0) as client:
        print(f"→ تسجيل الدخول ({ADMIN_EMAIL})...")
        r = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  ✅ توكن صالح تم الحصول عليه.")

        print("→ رفع الفاتورة عبر POST /ai/documents/analyze (البوابة الحقيقية عبر core-api)...")
        r = client.post(
            "/ai/documents/analyze",
            headers=headers,
            params={"company_currency": "IQD"},
            files={"file": ("invoice.png", image_bytes, "image/png")},
        )
        r.raise_for_status()
        job = r.json()
        job_id = job["id"] if "id" in job else job.get("job_id")
        print(f"  ✅ 202 Accepted — job_id={job_id}")

        print("→ استطلاع حالة job (حتى status=done)...")
        draft_id = None
        for attempt in range(30):
            r = client.get(f"/ai/documents/jobs/{job_id}", headers=headers)
            r.raise_for_status()
            status_body = r.json()
            status = status_body.get("status")
            print(f"  [{attempt + 1}] status={status}")
            if status == "done":
                draft_id = status_body.get("draft_id") or status_body.get("extraction_draft_id")
                break
            if status == "failed":
                print(f"  ❌ فشل الـjob: {status_body}", file=sys.stderr)
                return 1
            time.sleep(1)

        if not draft_id:
            print("  ❌ لم يكتمل الـjob خلال 30 محاولة — راجع سجلات ai-platform.", file=sys.stderr)
            return 1

        print(f"→ جلب المسودة النهائية (draft_id={draft_id})...")
        r = client.get(f"/ai/drafts/{draft_id}", headers=headers)
        r.raise_for_status()
        draft = r.json()

        matched = draft.get("matched_supplier_id")
        print("\n" + "=" * 60)
        if matched:
            print(f"✅ نجاح — matched_supplier_id = {matched}")
            print("   TASK-AI-04 يعمل فعلياً E2E عبر الشبكة الحقيقية.")
        else:
            print("❌ matched_supplier_id فارغ (None) — المطابقة لم تحدث.")
            print("   محتوى المسودة الكامل للتشخيص:")
            print(draft)
        print("=" * 60)
        return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
