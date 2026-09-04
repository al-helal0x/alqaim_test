import { apiFetch, apiFetchMultipart } from "@/api-client/http";
import type {
  AiDocumentJob,
  AiDraftCorrections,
  AiInvoiceDraft,
  EntitySuggestion,
} from "./ai-documents-types";

// كل المسارات أدناه من ai_proxy_router.py الفعلي (راجع 00_CONTRACT_مشترك.md)
// — الأساس "/ai" ثابت ومؤكَّد من الكود، بخلاف العقد السابق الافتراضي.

/**
 * رفع مستند لتحليله عبر AI. company_id يُحقَن من الجلسة تلقائياً في core-api
 * — لا يُرسَل هنا. company_currency اختياري، القيمة الافتراضية في core-api
 * نفسه "IQD" فلا حاجة لإرسالها إن لم تُحدَّد.
 */
export function analyzeDocument(file: File, companyCurrency?: string): Promise<AiDocumentJob> {
  const formData = new FormData();
  formData.append("file", file);
  const query = companyCurrency ? `?company_currency=${encodeURIComponent(companyCurrency)}` : "";
  return apiFetchMultipart<AiDocumentJob>(`/ai/documents/analyze${query}`, formData);
}

/** حالة مهمة التحليل (لِـ Polling أثناء status !== "completed"|"failed"). */
export function getDocumentJobStatus(jobId: string): Promise<AiDocumentJob> {
  return apiFetch<AiDocumentJob>(`/ai/documents/jobs/${encodeURIComponent(jobId)}`);
}

/** جلب المسودة الكاملة بعد اكتمال التحليل (باستخدام draft_id من AiDocumentJob). */
export function getDraft(draftId: string): Promise<AiInvoiceDraft> {
  return apiFetch<AiInvoiceDraft>(`/ai/drafts/${encodeURIComponent(draftId)}`);
}

/**
 * إرسال تصحيحات المستخدم اليدوية. الجسم dict خام يمرّره core-api كما هو —
 * الاستجابة 201 بلا جسم مفيد للعميل فنعيد void.
 */
export function submitDraftCorrections(draftId: string, corrections: AiDraftCorrections): Promise<void> {
  return apiFetch<void>(`/ai/drafts/${encodeURIComponent(draftId)}/corrections`, {
    method: "POST",
    body: corrections,
  });
}

/**
 * اعتماد نهائي — بلا جسم من العميل (reviewer_user_id يُحقَن من الجلسة).
 * الاستجابة unknown لأن core-api يمرّر استجابة ai-platform خاماً (راجع العقد).
 */
export function confirmDraft(draftId: string): Promise<unknown> {
  return apiFetch<unknown>(`/ai/drafts/${encodeURIComponent(draftId)}/confirm`, { method: "POST" });
}

/** رفض المسودة — بلا جسم أيضاً، نفس ملاحظة الاستجابة unknown. */
export function rejectDraft(draftId: string): Promise<unknown> {
  return apiFetch<unknown>(`/ai/drafts/${encodeURIComponent(draftId)}/reject`, { method: "POST" });
}

/**
 * اقتراحات كيانات (مثل مطابقة اسم مورّد نصي). ملاحظة من العقد: تبسيط مؤقت
 * غير مكتمل التكامل مع partners/catalog الفعلية — تحسين اختياري فقط، لا
 * يُبنى عليه الاعتماد الأساسي لاختيار المورّد/الفرع.
 */
export function getEntitySuggestions(entityType: string, text: string): Promise<EntitySuggestion[]> {
  const query = new URLSearchParams({ text });
  return apiFetch<EntitySuggestion[]>(`/ai/entities/${encodeURIComponent(entityType)}/suggestions?${query}`);
}
