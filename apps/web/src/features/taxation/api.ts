import { apiFetch } from "@/api-client/http";
import type { TaxCalculationResponse, TaxRateResponse } from "@/api-client/types";

export function listTaxRates() {
  return apiFetch<TaxRateResponse[]>("/tax-rates");
}

export function createTaxRate(payload: { code: string; name: string; rate_percent: string }) {
  return apiFetch<TaxRateResponse>("/tax-rates", { method: "POST", body: payload });
}

export function calculateTax(payload: { base_amount: string; tax_rate_id: string }) {
  return apiFetch<TaxCalculationResponse>("/tax-rates/calculate", {
    method: "POST",
    body: payload,
  });
}
