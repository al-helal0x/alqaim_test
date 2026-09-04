import { apiFetch } from "@/api-client/http";
import type { BankAccountResponse, PaymentResponse, ReceiptResponse } from "@/api-client/types";

export function listBankAccounts() {
  return apiFetch<BankAccountResponse[]>("/bank-accounts");
}

export function createBankAccount(payload: {
  name: string;
  bank_name?: string;
  account_number?: string;
  currency_code?: string;
  opening_balance?: string;
}) {
  return apiFetch<BankAccountResponse>("/bank-accounts", { method: "POST", body: payload });
}

export function listPayments() {
  return apiFetch<PaymentResponse[]>("/payments");
}

export function createPayment(payload: {
  supplier_id: string;
  amount: string;
  currency_code?: string;
  method?: string;
  bank_account_id?: string;
  reference_invoice_id?: string;
}) {
  return apiFetch<PaymentResponse>("/payments", { method: "POST", body: payload });
}

export function listReceipts() {
  return apiFetch<ReceiptResponse[]>("/receipts");
}

export function createReceipt(payload: {
  customer_id: string;
  amount: string;
  currency_code?: string;
  method?: string;
  bank_account_id?: string;
  reference_invoice_id?: string;
}) {
  return apiFetch<ReceiptResponse>("/receipts", { method: "POST", body: payload });
}
