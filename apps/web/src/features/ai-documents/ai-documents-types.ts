// نسخة حرفية من 00_CONTRACT_مشترك.md — لا تُعدَّل هنا. أي تغيير مطلوب على
// الأنواع يجب أن يبدأ من العقد المشترك نفسه أولاً (راجع "نقطة مفتوحة صريحة"
// في نهاية العقد بخصوص شكل حقول المسودة وتسمية مفاتيح corrections).

export type AiJobStatus = "pending" | "processing" | "completed" | "failed";

export type AiDocumentJob = {
  job_id: string;
  status: AiJobStatus;
  draft_id?: string | null; // يظهر عند completed غالباً — افتراض معقول غير مؤكَّد من الكود
  error_message?: string | null;
};

export type AiFieldConfidence = "high" | "medium" | "low";

/** شكل الحقل داخل المسودة — **افتراض** (ai-platform خارج نطاقنا كلياً، لا OpenAPI متاح لدرافت الفاتورة تحديداً بعد). */
export type AiDraftField<T = string> = {
  value: T | null;
  confidence: AiFieldConfidence;
};

export type AiDraftLine = {
  description: AiDraftField;
  quantity: AiDraftField;
  unit_price: AiDraftField;
};

export type AiDraftStatus = "pending_review" | "confirmed" | "rejected";

export type AiInvoiceDraft = {
  draft_id: string;
  status: AiDraftStatus;
  document_type?: string; // البوابة عامة لكل المستندات، لا للفواتير فقط
  supplier_name: AiDraftField;
  invoice_number: AiDraftField;
  invoice_date: AiDraftField;
  total_amount: AiDraftField;
  lines: AiDraftLine[];
};

/** خريطة تصحيحات مسطّحة: مفتاح -> قيمة نصية. تشمل تصحيح حقول AI (مثل
 * "invoice_number") وأيضاً حقول لا يستخرجها AI أصلاً مثل "supplier_id"،
 * "branch_id". **تسمية المفاتيح افتراض يحتاج تأكيداً من فريق ai-platform
 * عند التكامل الفعلي** — إن اختلفت، التعديل يقتصر على `ai-api.ts` وموقع
 * بناء الخريطة في `ai-draft-merge.ts`، لا على الشاشة (الجزء ب) لأنها تتعامل
 * مع دالة `buildCorrections()` لا مع المفاتيح مباشرة.
 */
export type AiDraftCorrections = Record<string, string>;

export type EntitySuggestion = {
  id: string;
  label: string;
  score?: number;
};
