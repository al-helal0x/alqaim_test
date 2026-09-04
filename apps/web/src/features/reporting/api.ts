import { apiFetch } from "@/api-client/http";

/**
 * TASK-BI-01 — أنواع مطابقة يدوياً لـ `business_pulse_dto.py` (Backend).
 *
 * ملاحظة صريحة: بقية أنواع هذا المشروع (`@/api-client/types`) مُولَّدة
 * تلقائياً عبر `npm run generate:api-types` (openapi-typescript) من
 * `openapi.json` لخادم يعمل فعلياً. لم يتوفّر خادم حي وقت تنفيذ هذه
 * المهمة داخل بيئة التنفيذ، فكُتبت هذه الأنواع يدوياً هنا بمطابقة تامة
 * لحقول `BusinessPulseResponse` في الـ DTO. **يجب استبدالها بإعادة توليد
 * حقيقية** (نفس الأمر أعلاه) في أول فرصة يعمل فيها الخادم فعلياً، بدل
 * إبقائها يدوية إلى الأبد — هذا قيد تنفيذ موثَّق، لا قرار تصميم دائم.
 */
export type SalesTrendPoint = {
  day: string; // YYYY-MM-DD
  total_amount: string;
};

export type TopProductRow = {
  product_id: string;
  total_quantity: string;
  total_amount: string;
};

export type CashAccountBalance = {
  bank_account_id: string;
  name: string;
  currency_code: string;
  balance: string;
};

export type LowStockItem = {
  product_id: string;
  warehouse_id: string;
  quantity: string;
};

export type ReceivablesAging = {
  bucket_0_30: string;
  bucket_31_60: string;
  bucket_61_plus: string;
};

export type BusinessPulseResponse = {
  company_id: string;
  period_days: number;
  generated_at: string;
  sales_trend: SalesTrendPoint[];
  sales_total_current_period: string;
  sales_total_previous_period: string;
  top_products: TopProductRow[];
  cash_accounts: CashAccountBalance[];
  cash_total: string;
  low_stock_items: LowStockItem[];
  receivables_aging: ReceivablesAging;
};

export function getBusinessPulse(periodDays: number = 7) {
  return apiFetch<BusinessPulseResponse>(`/reports/business-pulse?period_days=${periodDays}`);
}
