"""يجعل `idor/` حزمة فرعية حقيقية (dotted module name فريد
`tests.integration.idor.conftest`) بدل الاعتماد على وضع `prepend` الافتراضي
لـpytest (بلا `__init__.py`) — الذي يُحمِّل `conftest.py` في مجلدات مختلفة
تحت **نفس الاسم المبهم** `conftest` في `sys.modules`.

⚠️ اكتشاف حقيقي عند دمج IDOR في `tests/integration/`: هذا التصادم كسر فعلياً
`tests/integration/test_sales_invoice_idempotent_posting.py` (يحتوي فعلياً
على `from conftest import _swap_pg_only_types_for_sqlite` — استيراد مطلَق
هش موجود مسبقاً في الكود الأصلي، لا شيء أضفته). قبل إضافة `idor/conftest.py`
كان هناك ملف واحد فقط باسم `conftest` في `sys.modules`، فعمل الاستيراد
المطلق دون مشاكل. بمجرد إضافة ملف ثانٍ بنفس الاسم `conftest.py`، يُصبح أي
استيراد مطلَق `import conftest` عرضة لإرجاع أياً من الملفين حسب ترتيب
التحميل — هذا الملف يُصلح ذلك جذرياً بجعل استيراد conftest الخاص بـIDOR
مؤهَّلاً بالكامل (`tests.integration.idor.conftest`)، فلا يتصادم أبداً مع
الاسم المبهم `conftest` الذي يعتمد عليه ذلك الملف الآخر.
"""
