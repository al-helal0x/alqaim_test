# docs/architecture

- `contracts.md` — عقود "يوم العقود" بين الوحدات (Ports/DTOs/Events). المرجع
  الإلزامي الأول لأي عضو جديد.
- `ADR-001-event-architecture-and-ai-platform-boundary.md` — حدود AI
  Platform، Outbox ≠ Event Bus، ترتيب حسم تعارضات #6×#10×#11×#12 (مُنجَز
  الآن — راجع `ADR-003` وSTATUS_20_TASKS.md §15).
- `ADR-002-governance-and-parallel-tracks.md` — تصنيف القرارات الثلاثي
  (Architecture/Integration Blocking/Technical Debt) وحوكمة المسارات
  المتوازية.
- `ADR-003-vertical-slice-strategy.md` — استراتيجية Vertical Slice، حالة
  الإنجاز الفعلية لتعارض #6×#10×#11×#12، والأولوية الحالية (Walk-in
  Customer + AI→Purchasing). **يُكمَّل بـ `ALQAIM_V2_MASTER_EXECUTION_PLAN.md`
  بجذر المستودع** للتفصيل التكتيكي (Tasks/Gates/أوامر تحقق).
- `PRODUCT_VISION.md` بجذر المستودع — المرجع الأعلى لسؤال "هل ما نبنيه
  يخدم المنتج؟"، منفصل عن هذه الوثائق المعمارية عمداً (راجع مقدمتها).
- الوثيقة الكاملة للمشروع (تحليل V1، الأولويات، تصميم النظام، قاعدة البيانات،
  الـ APIs، تقسيم الفريق...) محفوظة في جذر الحزمة: `AlQaim_V2_Blueprint.md`.
