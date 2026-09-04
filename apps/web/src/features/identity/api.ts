import { apiFetch } from "@/api-client/http";
import type { TokenResponse } from "@/api-client/types";

export type RegisterCompanyPayload = {
  company_name: string;
  default_currency: string;
  admin_full_name: string;
  admin_email: string;
  admin_password: string;
};

export type LoginPayload = {
  email: string;
  password: string;
  company_id?: string;
};

export function registerCompany(payload: RegisterCompanyPayload) {
  return apiFetch<TokenResponse>("/auth/register-company", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function login(payload: LoginPayload) {
  return apiFetch<TokenResponse>("/auth/login", { method: "POST", body: payload, auth: false });
}
