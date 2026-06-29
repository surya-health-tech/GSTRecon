export type MatchConfidence = "high" | "low" | "none";

const FIELD_HEADER_PATTERNS: Record<string, string[]> = {
  voucher_number: ["voucher no", "voucher number", "voucher #", "vch no", "voucher"],
  company_gstin: ["company gstin", "gstin", "company gst no", "company gstin no", "gstin/uin"],
  supplier_name: ["supplier name", "vendor name", "party account", "party name", "vendor", "supplier"],
  supplier_gstin: [
    "supplier gstin",
    "vendor gstin",
    "party gstin",
    "gstin of supplier",
    "supplier gst no",
    "vendor gst no",
  ],
  supplier_invoice_no: [
    "supplier invoice no",
    "supplier bill no",
    "invoice #",
    "invoice number",
    "bill no",
    "invoice no",
    "bill number",
    "supplier inv no",
  ],
  supplier_invoice_date: [
    "supplier invoice date",
    "supplier bill date",
    "invoice date",
    "bill date",
    "inv date",
  ],
  taxable_amount: ["taxable amount", "gst taxable value", "taxable value", "sub total", "subtotal", "taxable amt"],
  igst: ["igst", "integrated tax", "igst amount"],
  sgst: ["sgst", "state tax", "state/ut tax", "state gst"],
  cgst: ["cgst", "central tax", "central gst"],
  total_tax: ["total tax", "tax amount", "total gst"],
  grand_total: ["grand total", "net amount", "total", "invoice value", "bill amount", "total amount"],
};

function normalizeHeader(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]/g, "");
}

function patternScore(normalizedHeader: string, pattern: string): number {
  const normPattern = normalizeHeader(pattern);
  if (!normPattern) return 0;
  if (normalizedHeader === normPattern) return 100;
  if (normalizedHeader.endsWith(normPattern) || normalizedHeader.startsWith(normPattern)) return 80;
  if (normPattern.includes(normalizedHeader) || normalizedHeader.includes(normPattern)) return 60;
  return 0;
}

export function autoMatchColumns(
  fieldCodes: string[],
  excelColumns: string[],
): { mappings: Record<string, string | null>; confidence: Record<string, MatchConfidence> } {
  const usedColumns = new Set<string>();
  const mappings: Record<string, string | null> = {};
  const confidence: Record<string, MatchConfidence> = {};
  const normalizedColumns = Object.fromEntries(excelColumns.map((col) => [col, normalizeHeader(col)]));

  for (const fieldCode of fieldCodes) {
    const patterns = FIELD_HEADER_PATTERNS[fieldCode] ?? [];
    let bestColumn: string | null = null;
    let bestScore = 0;

    for (const col of excelColumns) {
      if (usedColumns.has(col)) continue;
      const normCol = normalizedColumns[col];
      for (const pattern of patterns) {
        const score = patternScore(normCol, pattern);
        if (score > bestScore) {
          bestScore = score;
          bestColumn = col;
        }
      }
    }

    if (bestColumn && bestScore >= 80) {
      mappings[fieldCode] = bestColumn;
      confidence[fieldCode] = "high";
      usedColumns.add(bestColumn);
    } else if (bestColumn && bestScore >= 60) {
      mappings[fieldCode] = bestColumn;
      confidence[fieldCode] = "low";
      usedColumns.add(bestColumn);
    } else {
      mappings[fieldCode] = null;
      confidence[fieldCode] = "none";
    }
  }

  return { mappings, confidence };
}

export function findDuplicateColumnMappings(mappings: Record<string, string | null>): string | null {
  const seen = new Map<string, string>();
  for (const [fieldCode, col] of Object.entries(mappings)) {
    if (!col) continue;
    if (seen.has(col)) {
      return `Column "${col}" is mapped to both ${seen.get(col)} and ${fieldCode}.`;
    }
    seen.set(col, fieldCode);
  }
  return null;
}
