"""تنفيذ IFileStorage فوق القرص المحلي — الخيار الافتراضي الآن (راجع التعليق
في platform_core/config.py حول سبب عدم استخدام MinIO/S3 بعد). آمن للمسارات:
لا نثق بأي جزء من اسم الملف القادم من المستخدم كمسار — نُنشئ اسم مخزَّن عشوائياً
بالكامل (uuid4) ونُبقي الاسم الأصلي كحقل بيانات منفصل في الجدول فقط.
"""
import os
import uuid
from pathlib import Path

from platform_core.config import get_settings


class LocalFileStorage:
    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir or get_settings().documents_storage_dir)

    def _resolve(self, storage_key: str) -> Path:
        # storage_key يأتي دائماً من save() (نتحكم به بالكامل) — لا مدخلات
        # مستخدم خام هنا، لكن نتحقق دفاعياً من عدم الخروج عن base_dir لأي سبب.
        path = (self._base_dir / storage_key).resolve()
        if self._base_dir.resolve() not in path.parents and path != self._base_dir.resolve():
            raise ValueError("storage_key غير صالح")
        return path

    async def save(self, *, company_id: str, key: str, content: bytes) -> str:
        storage_key = f"{company_id}/{uuid.uuid4().hex}_{key}"
        path = self._resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await _run_blocking(path.write_bytes, content)
        return storage_key

    async def load(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        if not path.is_file():
            raise FileNotFoundError(storage_key)
        return await _run_blocking(path.read_bytes)

    async def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        try:
            await _run_blocking(os.remove, path)
        except FileNotFoundError:
            pass


async def _run_blocking(func, *args):
    """عمليات القرص هنا متزامنة (I/O بسيط، حجم مرفقات محدود) — نُشغّلها في
    Thread Pool حتى لا تحجب حلقة أحداث asyncio تحت حمل متزامن."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)
