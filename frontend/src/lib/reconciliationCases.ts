import { downloadAuthenticatedFile } from "../api/http";

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export function formatTaxPeriod(month: number, year: number): string {
  const name = MONTH_NAMES[month - 1] ?? String(month);
  return `${name} ${year}`;
}

export function formatTaxPeriodShort(month: number, year: number): string {
  return `${String(month).padStart(2, "0")}/${year}`;
}

export const CASE_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  files_uploaded: "Files Uploaded",
  processing: "Processing",
  processed: "Processed",
  review_pending: "Review Pending",
  completed: "Completed",
  error: "Error",
};

export const CASE_STATUS_COLORS: Record<string, "default" | "info" | "warning" | "success" | "error"> = {
  draft: "default",
  files_uploaded: "info",
  processing: "warning",
  processed: "success",
  review_pending: "warning",
  completed: "success",
  error: "error",
};

export const CATEGORY_LABELS: Record<string, string> = {
  matched_with_books: "Matched with Books",
  amount_mismatch: "Amount Mismatch",
  portal_open: "Portal Open Items",
  books_open: "Books Open Items",
};

export const CATEGORY_COLORS: Record<string, "default" | "info" | "warning" | "success" | "error"> = {
  matched_with_books: "success",
  amount_mismatch: "warning",
  portal_open: "info",
  books_open: "error",
};

export const CASE_STATUS_OPTIONS = Object.entries(CASE_STATUS_LABELS).map(([value, label]) => ({
  value,
  label,
}));

export const RECORD_TABS = [
  { key: "summary", label: "Summary", category: null },
  { key: "all", label: "All Records", category: null },
  { key: "matched_with_books", label: "Matched with Books", category: "matched_with_books" },
  { key: "amount_mismatch", label: "Amount Mismatch", category: "amount_mismatch" },
  { key: "portal_open", label: "Portal Open Items", category: "portal_open" },
  { key: "books_open", label: "Books Open Items", category: "books_open" },
] as const;

export function currentTaxPeriod(): { month: number; year: number } {
  const now = new Date();
  return { month: now.getMonth() + 1, year: now.getFullYear() };
}

export function formatAmount(value: unknown): string {
  const num = Number(value ?? 0);
  if (Number.isNaN(num)) return "0.00";
  return num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export const MASTER_COMPARISON_FIELDS = [
  { label: "Voucher Number", key: "voucher_number", numeric: false },
  { label: "Company GSTIN", key: "company_gstin", numeric: false },
  { label: "Supplier Name", key: "supplier_name", numeric: false },
  { label: "Supplier GSTIN", key: "supplier_gstin", numeric: false },
  { label: "Supplier Invoice No", key: "supplier_invoice_no", numeric: false },
  { label: "Supplier Invoice Date", key: "supplier_invoice_date", numeric: false },
  { label: "Taxable Amount", key: "taxable_amount", numeric: true },
  { label: "IGST", key: "igst", numeric: true },
  { label: "SGST", key: "sgst", numeric: true },
  { label: "CGST", key: "cgst", numeric: true },
  { label: "Total Tax", key: "total_tax", numeric: true },
  { label: "Grand Total", key: "grand_total", numeric: true },
] as const;

export function formatComparisonValue(
  data: Record<string, unknown> | null | undefined,
  key: string,
  numeric: boolean,
): string {
  if (!data) return "—";
  if (key === "total_tax" && numeric) {
    const total = Number(data.total_tax ?? 0);
    if (total !== 0) return formatAmount(total);
    const computed =
      Number(data.igst ?? 0) + Number(data.cgst ?? 0) + Number(data.sgst ?? 0);
    return formatAmount(computed);
  }
  const value = data[key];
  if (numeric) return formatAmount(value);
  const text = String(value ?? "").trim();
  return text || "—";
}

export async function exportCaseTabExcel(caseId: number, tabKey: string, caseName: string): Promise<void> {
  const safeName = caseName.replace(/[^\w.\- ]/g, "_").trim().slice(0, 60) || "case";
  const tabPart = tabKey.replace(/[^\w.\- ]/g, "_");
  await downloadAuthenticatedFile(
    `/app/reconciliation-cases/${caseId}/export?tab=${encodeURIComponent(tabKey)}`,
    `${safeName}_${tabPart}.xlsx`,
  );
}
