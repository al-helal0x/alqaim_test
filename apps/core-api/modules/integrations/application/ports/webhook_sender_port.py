from typing import Protocol


class IWebhookSender(Protocol):
    async def send(
        self, *, url: str, payload: dict, secret: str
    ) -> tuple[bool, int | None, str | None]:
        """يُرسِل payload كـ JSON إلى url موقَّعاً بـ HMAC. يُعيد
        (success, status_code, error_message) — لا يرفع استثناءً أبداً (كل
        فشل شبكي/HTTP يُترجَم لقيمة إرجاع) حتى لا يُسقِط باقي المشتركين عند
        فشل واحد منهم أثناء البث."""
        ...
