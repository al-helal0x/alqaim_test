import { apiFetch } from "@/api-client/http";
import type {
  LineItemRequest,
  PageOfQuotationResponse,
  PageOfSalesInvoiceResponse,
  PageOfSalesOrderResponse,
  QuotationResponse,
  SalesInvoiceResponse,
  SalesOrderResponse,
} from "@/api-client/types";

export function listQuotations(page = 1) {
  return apiFetch<PageOfQuotationResponse>(`/quotations?page=${page}&page_size=50`);
}

export function createQuotation(payload: { partner_id: string; currency?: string; lines: LineItemRequest[] }) {
  return apiFetch<QuotationResponse>("/quotations", { method: "POST", body: payload });
}

export function updateQuotationStatus(quotationId: string, status: string) {
  return apiFetch<QuotationResponse>(`/quotations/${quotationId}/status`, {
    method: "POST",
    body: { status },
  });
}

export function listSalesOrders(page = 1) {
  return apiFetch<PageOfSalesOrderResponse>(`/sales-orders?page=${page}&page_size=50`);
}

export function createSalesOrder(payload: {
  partner_id: string;
  quotation_id?: string | null;
  currency?: string;
  lines: LineItemRequest[];
}) {
  return apiFetch<SalesOrderResponse>("/sales-orders", { method: "POST", body: payload });
}

export function confirmSalesOrder(orderId: string) {
  return apiFetch<SalesOrderResponse>(`/sales-orders/${orderId}/confirm`, { method: "POST" });
}

export function listSalesInvoices(page = 1) {
  return apiFetch<PageOfSalesInvoiceResponse>(`/sales-invoices?page=${page}&page_size=50`);
}

export function createSalesInvoice(payload: {
  partner_id: string;
  warehouse_id: string;
  sales_order_id?: string | null;
  currency?: string;
  discount_amount?: string;
  lines: LineItemRequest[];
}) {
  return apiFetch<SalesInvoiceResponse>("/sales-invoices", { method: "POST", body: payload });
}

export function postSalesInvoice(invoiceId: string) {
  return apiFetch<SalesInvoiceResponse>(`/sales-invoices/${invoiceId}/post`, { method: "POST" });
}
