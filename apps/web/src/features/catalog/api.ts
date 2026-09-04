import { apiFetch } from "@/api-client/http";
import type {
  CategoryResponse,
  PageOfProductResponse,
  PriceListResponse,
  ProductResponse,
  ProductType,
  UomResponse,
} from "@/api-client/types";

export function listProducts(params: { search?: string; categoryId?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.categoryId) query.set("category_id", params.categoryId);
  query.set("page", String(params.page ?? 1));
  query.set("page_size", "50");
  return apiFetch<PageOfProductResponse>(`/products?${query.toString()}`);
}

export function createProduct(payload: {
  sku: string;
  name: string;
  product_type?: ProductType;
  category_id?: string | null;
  base_uom_id: string;
  sale_price?: string;
  purchase_price?: string;
  track_inventory?: boolean;
}) {
  return apiFetch<ProductResponse>("/products", { method: "POST", body: payload });
}

export function listCategories() {
  return apiFetch<CategoryResponse[]>("/categories");
}

export function createCategory(payload: { name: string; parent_id?: string | null }) {
  return apiFetch<CategoryResponse>("/categories", { method: "POST", body: payload });
}

export function listUnitsOfMeasure() {
  return apiFetch<UomResponse[]>("/units-of-measure");
}

export function createUnitOfMeasure(payload: { code: string; name: string }) {
  return apiFetch<UomResponse>("/units-of-measure", { method: "POST", body: payload });
}

export function createPriceList(payload: { name: string; currency?: string; is_default?: boolean }) {
  return apiFetch<PriceListResponse>("/price-lists", { method: "POST", body: payload });
}
