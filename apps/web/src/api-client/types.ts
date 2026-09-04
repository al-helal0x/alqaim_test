// أنواع مولَّدة فعلياً من OpenAPI الحقيقي لـ core-api (packages/api-types) —
// وليست مكتوبة يدوياً بعد اليوم. تُعاد توليدها عبر:
//   npm run generate:api-types   (core-api يجب أن يعمل محلياً ويصدّر /openapi.json)
import type { components } from "@alqaim/api-types";

type Schemas = components["schemas"];

export type TokenResponse = Schemas["TokenResponse"];
export type CompanyResponse = Schemas["CompanyResponse"];
export type BranchResponse = Schemas["BranchResponse"];
export type WarehouseResponse = Schemas["WarehouseResponse"];

export type AccountType = Schemas["AccountCreateRequest"]["account_type"];
export type AccountNormalBalance = Schemas["AccountCreateRequest"]["normal_balance"];
export type AccountResponse = Schemas["AccountResponse"];
export type FiscalPeriodResponse = Schemas["FiscalPeriodResponse"];
export type FiscalYearResponse = Schemas["FiscalYearResponse"];
export type JournalEntryLineResponse = Schemas["JournalEntryLineResponse"];
export type JournalEntryResponse = Schemas["JournalEntryResponse"];
export type TrialBalanceRow = Schemas["TrialBalanceRow"];
export type TrialBalanceResponse = Schemas["TrialBalanceResponse"];
export type StatementRow = Schemas["StatementRowResponse"];
export type IncomeStatementResponse = Schemas["IncomeStatementResponse"];
export type BalanceSheetResponse = Schemas["BalanceSheetResponse"];
export type TaxRateResponse = Schemas["TaxRateResponse"];
export type TaxCalculationResponse = Schemas["TaxCalculationResponse"];

export type PartnerType = Schemas["PartnerCreateRequest"]["partner_type"];
export type PartnerResponse = Schemas["PartnerResponse"];
export type PageOfPartnerResponse = Schemas["Page_PartnerResponse_"];

export type ProductType = Schemas["ProductCreateRequest"]["product_type"];
export type ProductResponse = Schemas["ProductResponse"];
export type PageOfProductResponse = Schemas["Page_ProductResponse_"];
export type CategoryResponse = Schemas["CategoryResponse"];
export type UomResponse = Schemas["UomResponse"];
export type PriceListResponse = Schemas["PriceListResponse"];
export type PriceListItemResponse = Schemas["PriceListItemResponse"];

export type StockBalanceResponse = Schemas["StockBalanceResponse"];
export type StockMovementResponse = Schemas["StockMovementResponse"];
export type StockTransferResponse = Schemas["StockTransferResponse"];
export type StockAdjustmentResponse = Schemas["StockAdjustmentResponse"];
export type PageOfStockBalanceResponse = Schemas["Page_StockBalanceResponse_"];
export type PageOfStockMovementResponse = Schemas["Page_StockMovementResponse_"];
export type MovementType = Schemas["RecordMovementRequest"]["movement_type"];

export type LineItemRequest = Schemas["LineItemRequest"];
export type LineItemResponse = Schemas["LineItemResponse"];

export type QuotationResponse = Schemas["QuotationResponse"];
export type PageOfQuotationResponse = Schemas["Page_QuotationResponse_"];
export type SalesOrderResponse = Schemas["SalesOrderResponse"];
export type PageOfSalesOrderResponse = Schemas["Page_SalesOrderResponse_"];
export type SalesInvoiceResponse = Schemas["SalesInvoiceResponse"];
export type PageOfSalesInvoiceResponse = Schemas["Page_SalesInvoiceResponse_"];
export type CreditNoteResponse = Schemas["CreditNoteResponse"];

export type PosSaleRequest = Schemas["PosSaleRequest"];
export type SessionResponse = Schemas["SessionResponse"];

export type PurchaseOrderResponse = Schemas["PurchaseOrderResponse"];
export type PurchaseOrderLineResponse = Schemas["PurchaseOrderLineResponse"];
export type PurchaseInvoiceResponse = Schemas["PurchaseInvoiceResponse"];

export type BankAccountResponse = Schemas["BankAccountResponse"];
export type PaymentResponse = Schemas["PaymentResponse"];
export type ReceiptResponse = Schemas["ReceiptResponse"];
