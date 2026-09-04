import { apiFetch } from "@/api-client/http";
import type {
  AccountNormalBalance,
  AccountResponse,
  AccountType,
  BalanceSheetResponse,
  FiscalYearResponse,
  IncomeStatementResponse,
  JournalEntryResponse,
  TrialBalanceResponse,
} from "@/api-client/types";

export function listAccounts() {
  return apiFetch<AccountResponse[]>("/accounts");
}

export function createAccount(payload: {
  code: string;
  name: string;
  account_type: AccountType;
  normal_balance: AccountNormalBalance;
  parent_id?: string | null;
  is_postable?: boolean;
}) {
  return apiFetch<AccountResponse>("/accounts", { method: "POST", body: payload });
}

export function seedDefaultChartOfAccounts() {
  return apiFetch<AccountResponse[]>("/accounts/seed-defaults", { method: "POST" });
}

export function listFiscalYears() {
  return apiFetch<FiscalYearResponse[]>("/fiscal-periods/years");
}

export function createFiscalYear(payload: {
  code: string;
  start_date: string;
  end_date: string;
  period_count?: number;
}) {
  return apiFetch<FiscalYearResponse>("/fiscal-periods/years", { method: "POST", body: payload });
}

export function closeFiscalPeriod(periodId: string) {
  return apiFetch<{ id: string; is_closed: boolean }>(`/fiscal-periods/${periodId}/close`, {
    method: "POST",
  });
}

export function listJournalEntries() {
  return apiFetch<JournalEntryResponse[]>("/journal-entries");
}

export function postManualJournalEntry(payload: {
  entry_date: string;
  memo?: string;
  currency?: string;
  lines: { account_id: string; debit?: string; credit?: string; description?: string }[];
}) {
  return apiFetch<JournalEntryResponse>("/journal-entries", { method: "POST", body: payload });
}

export function getJournalEntry(entryId: string) {
  return apiFetch<JournalEntryResponse>(`/journal-entries/${entryId}`);
}

export function getTrialBalance(fiscalPeriodId: string) {
  return apiFetch<TrialBalanceResponse>(
    `/reports/trial-balance?fiscal_period_id=${encodeURIComponent(fiscalPeriodId)}`
  );
}

export function getIncomeStatement(fiscalYearId: string) {
  return apiFetch<IncomeStatementResponse>(
    `/reports/income-statement?fiscal_year_id=${encodeURIComponent(fiscalYearId)}`
  );
}

export function getBalanceSheet(fiscalYearId: string) {
  return apiFetch<BalanceSheetResponse>(
    `/reports/balance-sheet?fiscal_year_id=${encodeURIComponent(fiscalYearId)}`
  );
}
