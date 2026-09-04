import { apiFetch } from "@/api-client/http";
import type { PageOfPartnerResponse, PartnerResponse, PartnerType } from "@/api-client/types";

export function listPartners(params: { partnerType?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.partnerType) query.set("partner_type", params.partnerType);
  query.set("page", String(params.page ?? 1));
  query.set("page_size", "50");
  return apiFetch<PageOfPartnerResponse>(`/partners?${query.toString()}`);
}

export function createPartner(payload: {
  name: string;
  partner_type?: PartnerType;
  tax_number?: string;
  phone?: string;
  email?: string;
  address?: string;
  credit_limit?: string;
  payment_terms_days?: number;
}) {
  return apiFetch<PartnerResponse>("/partners", { method: "POST", body: payload });
}
