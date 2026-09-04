import { apiFetch } from "@/api-client/http";
import type { PurchaseInvoiceResponse, PurchaseOrderResponse } from "@/api-client/types";

export type PurchaseOrderLineInput = {
  product_id: string;
  description: string;
  quantity: string;
  unit_price: string;
};

export function listPurchaseOrders() {
  return apiFetch<PurchaseOrderResponse[]>("/purchase-orders");
}

export function createPurchaseOrder(payload: {
  branch_id: string;
  supplier_id: string;
  currency_code?: string;
  tax_amount?: string;
  discount_amount?: string;
  lines: PurchaseOrderLineInput[];
}) {
  return apiFetch<PurchaseOrderResponse>("/purchase-orders", { method: "POST", body: payload });
}

export function confirmPurchaseOrder(orderId: string) {
  return apiFetch<PurchaseOrderResponse>(`/purchase-orders/${orderId}/confirm`, { method: "POST" });
}

export function cancelPurchaseOrder(orderId: string) {
  return apiFetch<PurchaseOrderResponse>(`/purchase-orders/${orderId}/cancel`, { method: "POST" });
}

export function receivePurchaseOrder(orderId: string, warehouseId: string) {
  return apiFetch<PurchaseOrderResponse>(
    `/purchase-orders/${orderId}/receive?warehouse_id=${encodeURIComponent(warehouseId)}`,
    { method: "POST" }
  );
}

export function listPurchaseInvoices() {
  return apiFetch<PurchaseInvoiceResponse[]>("/purchase-invoices");
}

export function createPurchaseInvoiceFromOrder(purchaseOrderId: string) {
  return apiFetch<PurchaseInvoiceResponse>("/purchase-invoices/from-order", {
    method: "POST",
    body: { purchase_order_id: purchaseOrderId },
  });
}

export function createStandalonePurchaseInvoice(payload: {
  branch_id: string;
  supplier_id: string;
  currency_code?: string;
  tax_amount?: string;
  discount_amount?: string;
  lines: PurchaseOrderLineInput[];
}) {
  return apiFetch<PurchaseInvoiceResponse>("/purchase-invoices", { method: "POST", body: payload });
}

export function postPurchaseInvoice(invoiceId: string) {
  return apiFetch<PurchaseInvoiceResponse>(`/purchase-invoices/${invoiceId}/post`, { method: "POST" });
}
