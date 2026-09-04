import { apiFetch } from "@/api-client/http";
import type { BranchResponse, WarehouseResponse } from "@/api-client/types";

export function listBranches() {
  return apiFetch<BranchResponse[]>("/branches");
}

export function createBranch(name: string) {
  return apiFetch<BranchResponse>("/branches", { method: "POST", body: { name } });
}

export function listWarehouses(branchId?: string) {
  const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
  return apiFetch<WarehouseResponse[]>(`/warehouses${query}`);
}

export function createWarehouse(branchId: string, name: string) {
  return apiFetch<WarehouseResponse>("/warehouses", {
    method: "POST",
    body: { branch_id: branchId, name },
  });
}
