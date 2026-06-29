from pathlib import Path

from app.services.gstr2b_auto_match import auto_match_gstr2b_columns
from app.services.gstr2b_excel import list_workbook_sheets, map_workbook_sheets, parse_sheet_data

content = Path("/tmp/portal.xlsx").read_bytes()
sheets = list_workbook_sheets(content, "portal.xlsx")
mapped = map_workbook_sheets(sheets)
print("Mapped tabs:", {k: v for k, v in mapped.items() if v})

fields = [
    "supplier_name",
    "supplier_gstin",
    "supplier_invoice_no",
    "supplier_invoice_date",
    "taxable_amount",
    "igst",
    "cgst",
    "sgst",
    "grand_total",
]

for tab in ["B2B", "B2BA", "B2B-CDNR", "B2B-CDNRA", "ECO", "ISD", "IMPG", "IMPSEZ", "IMPSEZA"]:
    sn = mapped.get(tab)
    if not sn:
        print(f"--- {tab}: NOT FOUND ---")
        continue
    cols, sample = parse_sheet_data(content, "portal.xlsx", sn)
    inc_note = tab in {"B2B-CDNR", "B2B-CDNRA"}
    mappings, confidence = auto_match_gstr2b_columns(fields, cols, include_note_type=inc_note, tab=tab)
    print(f"--- {tab} ({sn}) cols={len(cols)} ---")
    print("  columns:", cols)
    for f in fields + (["note_type"] if inc_note else []):
        col = mappings.get(f)
        samp = sample.get(col, "") if col else ""
        print(f"  {f}: {col!r} [{confidence.get(f)}] sample={samp!r}")
