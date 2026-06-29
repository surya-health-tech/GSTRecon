export const GSTR2B_TABS = [
  "B2B",
  "B2BA",
  "B2B-CDNR",
  "B2B-CDNRA",
  "ECO",
  "ECOA",
  "ISD",
  "ISDA",
  "IMPG",
  "IMPGA",
  "IMPSEZ",
  "IMPSEZA",
] as const;

export type Gstr2bTab = (typeof GSTR2B_TABS)[number];

export const CDNR_TABS = new Set<Gstr2bTab>(["B2B-CDNR", "B2B-CDNRA"]);

export const OPTIONAL_GSTR2B_FIELDS = new Set(["company_gstin", "total_tax"]);

/** Stored value when a field is not available in the tab's Excel sheet. */
export const GSTR2B_NA_VALUE = "__NA__";
export const GSTR2B_NA_LABEL = "N/A";

export function isGstr2bMappingSet(value: string | null | undefined): boolean {
  return Boolean(value && value.trim());
}

export function isGstr2bNaMapping(value: string | null | undefined): boolean {
  return value === GSTR2B_NA_VALUE;
}

export function serializeGstr2bColumnMappings(
  mappings: Record<string, string | null>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(mappings).filter((entry): entry is [string, string] => isGstr2bMappingSet(entry[1])),
  ) as Record<string, string>;
}

export const NOTE_TYPE_FIELD = {
  code: "note_type",
  name: "Note Type",
  required: true,
  helperText:
    "Credit Note (C) reduces invoice values and tax amounts. Debit Note (D) increases them. Sign adjustment is applied during import/reconciliation.",
};
