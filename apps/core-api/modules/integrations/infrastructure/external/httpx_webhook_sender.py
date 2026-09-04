"""تنفيذ IWebhookSender عبر httpx — يوقِّع كل حمولة بـ HMAC-SHA256 على سر
الاشتراك الخاص بالعميل (نفس نمط توقيع Stripe/GitHub Webhooks الشائع)، حتى
يستطيع العميل الخارجي التحقق أن الطلب فعلاً من AlQaim وليس منتحَلاً."""
import hashlib
import hmac
import json

import httpx

TIMEOUT_SECONDS = 10.0


class HttpxWebhookSender:
    async def send(
        self, *, url: str, payload: dict, secret: str
    ) -> tuple[bool, int | None, str | None]:
        body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-AlQaim-Signature": f"sha256={signature}",
                    },
                )
            success = 200 <= response.status_code < 300
            return success, response.status_code, None if success else response.text[:500]
        except httpx.RequestError as exc:
            return False, None, str(exc)
