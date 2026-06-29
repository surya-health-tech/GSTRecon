import type { MatchConfidence } from "./columnAutoMatch";
import { isGstr2bMappingSet, isGstr2bNaMapping } from "./gstr2bTabs";

const GSTR2B_FIELD_PATTERNS: Record<string, string[]> = {
  company_gstin: ["company gstin", "gstin of recipient", "recipient gstin", "gstin"],
  supplier_name: ["trade/legal name", "trade legal name", "legal name", "supplier name", "name of supplier"],
  supplier_gstin: ["gstin of supplier", "supplier gstin", "gstin"],
  supplier_invoice_no: ["invoice number", "invoice no", "note number", "document number", "document no", "invoice #", "number"],
  supplier_invoice_date: ["invoice date", "note date", "document date", "date"],
  taxable_amount: ["taxable value (₹)", "taxable value", "taxable amount", "taxable value(rs)"],
  igst: ["integrated tax(₹)", "integrated tax", "igst", "integrated tax amount"],
  sgst: ["state/ut tax(₹)", "state/ut tax", "state tax", "sgst", "state/ut tax amount"],
  cgst: ["central tax(₹)", "central tax", "cgst", "central tax amount"],
  total_tax: ["total tax", "tax amount", "total gst", "total tax(₹)"],
  grand_total: ["invoice value(₹)", "invoice value", "note value (₹)", "note value", "document value(₹)", "document value", "grand total", "total invoice value"],
};

const AMENDMENT_TABS = new Set(["B2BA", "B2B-CDNRA", "ECOA", "ISDA", "IMPGA", "IMPSEZA"]);

const NOTE_TYPE_PATTERNS = ["note type", "credit/debit note type", "credit debit note type", "type of note"];

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

export function autoMatchGstr2bColumns(
  fieldCodes: string[],
  excelColumns: string[],
  includeNoteType = false,
  tab?: string,
): { mappings: Record<string, string | null>; confidence: Record<string, MatchConfidence> } {
  const usedColumns = new Set<string>();
  const mappings: Record<string, string | null> = {};
  const confidence: Record<string, MatchConfidence> = {};
  const normalizedColumns = Object.fromEntries(excelColumns.map((col) => [col, normalizeHeader(col)]));

  for (const fieldCode of fieldCodes) {
    const patterns = GSTR2B_FIELD_PATTERNS[fieldCode] ?? [];
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
      let chosen = bestColumn;
      if (tab && AMENDMENT_TABS.has(tab)) {
        const base = chosen.replace(" (2)", "").trim();
        const revised = excelColumns.find((c) => c.startsWith(base) && c.includes("(2)"));
        if (
          revised &&
          ["supplier_invoice_no", "supplier_invoice_date", "igst", "cgst", "sgst", "grand_total"].includes(fieldCode)
        ) {
          chosen = revised;
        }
      }
      mappings[fieldCode] = chosen;
      confidence[fieldCode] = "high";
      usedColumns.add(chosen);
    } else if (bestColumn && bestScore >= 60) {
      mappings[fieldCode] = bestColumn;
      confidence[fieldCode] = "low";
      usedColumns.add(bestColumn);
    } else {
      mappings[fieldCode] = null;
      confidence[fieldCode] = "none";
    }
  }

  if (includeNoteType) {
    let bestColumn: string | null = null;
    let bestScore = 0;
    for (const col of excelColumns) {
      if (usedColumns.has(col)) continue;
      const normCol = normalizedColumns[col];
      for (const pattern of NOTE_TYPE_PATTERNS) {
        const score = patternScore(normCol, pattern);
        if (score > bestScore) {
          bestScore = score;
          bestColumn = col;
        }
      }
    }
    if (bestColumn && bestScore >= 60) {
      mappings.note_type = bestColumn;
      confidence.note_type = bestScore >= 80 ? "high" : "low";
    } else {
      mappings.note_type = null;
      confidence.note_type = "none";
    }
  }

  return { mappings, confidence };
}

export function isTotalTaxDerivable(mappings: Record<string, string | null>): boolean {
  const mapped = (code: string) => isGstr2bMappingSet(mappings[code]) && !isGstr2bNaMapping(mappings[code]);
  return mapped("igst") && mapped("cgst") && mapped("sgst");
}

export function isFieldRequiredForGstr2b(
  fieldCode: string,
  isRequired: boolean,
  mappings: Record<string, string | null>,
): boolean {
  if (!isRequired) return false;
  if (isGstr2bNaMapping(mappings[fieldCode])) return false;
  if (fieldCode === "company_gstin") return false;
  if (fieldCode === "total_tax") {
    if (isGstr2bMappingSet(mappings.total_tax) && !isGstr2bNaMapping(mappings.total_tax)) return false;
    return !isTotalTaxDerivable(mappings);
  }
  return !isGstr2bMappingSet(mappings[fieldCode]);
}

export function findDuplicateColumnMappingsForTab(
  mappings: Record<string, string | null>,
): string | null {
  const seen = new Map<string, string>();
  for (const [fieldCode, col] of Object.entries(mappings)) {
    if (!col || !isGstr2bMappingSet(col) || isGstr2bNaMapping(col)) continue;
    if (seen.has(col)) {
      return `Column "${col}" is mapped to both ${seen.get(col)} and ${fieldCode}.`;
    }
    seen.set(col, fieldCode);
  }
  return null;
}
