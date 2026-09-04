import { clearTokens, getAccessToken } from "./auth-storage";
import { getApiBaseUrl } from "./server-config";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean; // إرفاق Authorization header — افتراضياً true
};

type MultipartRequestOptions = {
  method?: "POST" | "PATCH";
  auth?: boolean; // إرفاق Authorization header — افتراضياً true
};

/**
 * حقل واحد من مصفوفة أخطاء التحقق التي يرجعها FastAPI/Pydantic لحالة 422 —
 * الشكل الفعلي هو `{detail: [{loc, msg, type}, ...]}` وليس نصاً واحداً.
 */
type FastApiValidationError = { loc?: (string | number)[]; msg?: string };

/**
 * يحوّل مصفوفة أخطاء 422 من FastAPI إلى نص عربي واحد قابل للعرض في البانر.
 * يعرض اسم الحقل (آخر عنصر في `loc`، متجاهلاً `body`/`query` إلخ) مع رسالة
 * كل خطأ، ويجمع عدة أخطاء بفاصلة إن وُجدت أكثر من حقل.
 */
export function formatValidationErrors(errors: FastApiValidationError[]): string {
  const parts = errors
    .map((e) => {
      const field = Array.isArray(e.loc)
        ? e.loc.filter((p) => p !== "body" && p !== "query" && p !== "path").at(-1)
        : undefined;
      const msg = e.msg || "قيمة غير صالحة";
      return field ? `${field}: ${msg}` : msg;
    })
    .filter(Boolean);
  return parts.length > 0 ? `بيانات غير صالحة — ${parts.join("، ")}` : "بيانات غير صالحة";
}

/**
 * منطق مشترك بين apiFetch وapiFetchMultipart: معالجة 401 بتسجيل خروج تلقائي،
 * ومعالجة الاستجابات غير الناجحة برسالة خطأ موحّدة. مستخرَج هنا لتفادي تكرار
 * نفس المنطق في كل دالة طلب جديدة (JSON أو multipart أو غيرها لاحقاً).
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "انتهت الجلسة — الرجاء تسجيل الدخول مجدداً");
  }

  if (!response.ok) {
    let detail = `طلب فاشل: ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      } else if (Array.isArray(data?.detail)) {
        // شكل أخطاء التحقق (422) من FastAPI/Pydantic — مصفوفة، وليس نصاً.
        // كانت تتسرب سابقاً كـ"طلب فاشل: 422" الخام بلا أي تفصيل.
        detail = formatValidationErrors(data.detail);
      }
    } catch {
      // تجاهل: بعض الأخطاء لا تحمل جسم JSON
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * عميل HTTP وحيد لكل core-api — Thin Client بالكامل (القسم 6.2): لا منطق
 * أعمال هنا، فقط تنسيق الطلب/الاستجابة ومعالجة 401 بتسجيل خروج تلقائي.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  return handleResponse<T>(response);
}

/**
 * مثل apiFetch لكن لرفع الملفات (multipart/form-data) — بلا Content-Type
 * يدوي عمداً: المتصفح يضبطه تلقائياً مع boundary الصحيح عند تمرير FormData
 * مباشرة لـ fetch. تشارك نفس معالجة 401/الأخطاء عبر handleResponse.
 */
export async function apiFetchMultipart<T>(
  path: string,
  formData: FormData,
  options: MultipartRequestOptions = {}
): Promise<T> {
  const { method = "POST", auth = true } = options;

  const headers: Record<string, string> = {};
  if (auth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method,
    headers,
    body: formData,
  });

  return handleResponse<T>(response);
}
