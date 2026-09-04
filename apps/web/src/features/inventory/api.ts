import { apiFetch } from "@/api-client/http";
import type {
  MovementType,
  PageOfStockBalanceResponse,
  PageOfStockMovementResponse,
  StockAdjustmentResponse,
  StockTransferResponse,
} from "@/api-client/types";

export function listStockBalances(params: { warehouseId?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.warehouseId) query.set("warehouse_id", params.warehouseId);
  query.set("page", String(params.page ?? 1));
  query.set("page_size", "50");
  return apiFetch<PageOfStockBalanceResponse>(`/inventory/balances?${query.toString()}`);
}

export function listStockMovements(
  params: { warehouseId?: string; productId?: string; page?: number } = {}
) {
  const query = new URLSearchParams();
  if (params.warehouseId) query.set("warehouse_id", params.warehouseId);
  if (params.productId) query.set("product_id", params.productId);
  query.set("page", String(params.page ?? 1));
  query.set("page_size", "50");
  return apiFetch<PageOfStockMovementResponse>(`/inventory/movements?${query.toString()}`);
}

export function recordMovement(payload: {
  warehouse_id: string;
  product_id: string;
  movement_type: MovementType;
  quantity: string;
  unit_cost?: string;
  notes?: string;
}) {
  return apiFetch("/inventory/movements", { method: "POST", body: payload });
}

export function createStockTransfer(payload: {
  from_warehouse_id: string;
  to_warehouse_id: string;
  product_id: string;
  quantity: string;
  notes?: string;
}) {
  return apiFetch<StockTransferResponse>("/inventory/transfers", { method: "POST", body: payload });
}

export function createStockAdjustment(payload: {
  warehouse_id: string;
  product_id: string;
  quantity_delta: string;
  reason: string;
}) {
  return apiFetch<StockAdjustmentResponse>("/inventory/adjustments", {
    method: "POST",
    body: payload,
  });
}
