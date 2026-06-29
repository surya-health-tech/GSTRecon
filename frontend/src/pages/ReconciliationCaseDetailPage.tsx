import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Grid,
  IconButton,
  Stack,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import EditOutlined from "@mui/icons-material/EditOutlined";
import FileDownloadOutlined from "@mui/icons-material/FileDownloadOutlined";
import KeyboardArrowDown from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUp from "@mui/icons-material/KeyboardArrowUp";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import { usePermissions } from "../auth/usePermissions";
import {
  CASE_STATUS_COLORS,
  CASE_STATUS_LABELS,
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  exportCaseTabExcel,
  formatAmount,
  formatComparisonValue,
  formatTaxPeriod,
  formatTaxPeriodShort,
  MASTER_COMPARISON_FIELDS,
  RECORD_TABS,
} from "../lib/reconciliationCases";

type CaseDetail = {
  id: number;
  case_name: string;
  client_id: number | null;
  client_name: string | null;
  tax_period_month: number;
  tax_period_year: number;
  status: string;
  gstr2b_original_filename: string | null;
  pr_original_filename: string | null;
  gstr2b_mapping_name: string | null;
  pr_mapping_name: string | null;
  summary_counts: Record<string, number>;
  error_message: string | null;
};

type CaseRecord = {
  id: number;
  category: string;
  match_status: string | null;
  remarks: string | null;
  portal_data: Record<string, unknown> | null;
  book_data: Record<string, unknown> | null;
  normalized: Record<string, unknown>;
};

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="h5" fontWeight={700}>
          {value.toLocaleString()}
        </Typography>
      </CardContent>
    </Card>
  );
}

function RecordRow({ record }: { record: CaseRecord }) {
  const [open, setOpen] = useState(false);
  const n = record.normalized;
  const hasBoth = Boolean(record.portal_data && record.book_data);

  return (
    <>
      <TableRow hover>
        <TableCell padding="checkbox">
          {hasBoth && (
            <IconButton size="small" onClick={() => setOpen((o) => !o)}>
              {open ? <KeyboardArrowUp fontSize="small" /> : <KeyboardArrowDown fontSize="small" />}
            </IconButton>
          )}
        </TableCell>
        <TableCell>
          <Chip size="small" label={CATEGORY_LABELS[record.category] ?? record.category} color={CATEGORY_COLORS[record.category] ?? "default"} />
        </TableCell>
        <TableCell>{String(n.company_gstin ?? "")}</TableCell>
        <TableCell>{String(n.supplier_name ?? "")}</TableCell>
        <TableCell>{String(n.supplier_gstin ?? "")}</TableCell>
        <TableCell>{String(n.supplier_invoice_no ?? "")}</TableCell>
        <TableCell>{String(n.supplier_invoice_date ?? "")}</TableCell>
        <TableCell align="right">{formatAmount(n.taxable_amount)}</TableCell>
        <TableCell align="right">{formatAmount(n.igst)}</TableCell>
        <TableCell align="right">{formatAmount(n.sgst)}</TableCell>
        <TableCell align="right">{formatAmount(n.cgst)}</TableCell>
        <TableCell align="right">{formatAmount(n.total_tax ?? n.portal_total_tax ?? n.book_total_tax)}</TableCell>
        <TableCell align="right">{formatAmount(n.grand_total)}</TableCell>
        <TableCell>{String(n.source ?? "")}</TableCell>
        <TableCell>{record.match_status ?? "—"}</TableCell>
        <TableCell>{record.remarks ?? "—"}</TableCell>
      </TableRow>
      {hasBoth && (
        <TableRow>
          <TableCell colSpan={16} sx={{ py: 0, borderBottom: open ? undefined : 0 }}>
            <Collapse in={open} timeout="auto" unmountOnExit>
              <Box sx={{ py: 2, px: 1 }}>
                <SideBySideComparison portal={record.portal_data} book={record.book_data} />
              </Box>
            </Collapse>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function SideBySideComparison({
  portal,
  book,
}: {
  portal: Record<string, unknown> | null;
  book: Record<string, unknown> | null;
}) {
  const cellSx = { py: 0.75, px: 1.5, fontSize: "0.8125rem" };
  const valueCellSx = {
    ...cellSx,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    whiteSpace: "nowrap" as const,
  };

  return (
    <Box
      sx={{
        maxWidth: 680,
        border: 1,
        borderColor: "divider",
        borderRadius: 1,
        overflow: "hidden",
        bgcolor: "background.paper",
      }}
    >
      <Table size="small" sx={{ tableLayout: "fixed", width: "100%" }}>
        <TableHead>
          <TableRow>
            <TableCell sx={{ ...cellSx, width: "34%", fontWeight: 600 }}>Master Field</TableCell>
            <TableCell sx={{ ...valueCellSx, width: "33%", fontWeight: 600 }} align="right">
              GSTR-2B
            </TableCell>
            <TableCell sx={{ ...valueCellSx, width: "33%", fontWeight: 600 }} align="right">
              Purchase Register
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {MASTER_COMPARISON_FIELDS.map(({ label, key, numeric }) => {
            const portalValue = formatComparisonValue(portal, key, numeric);
            const bookValue = formatComparisonValue(book, key, numeric);
            const differs = portalValue !== bookValue;
            return (
              <TableRow key={key} sx={differs ? { bgcolor: "action.hover" } : undefined}>
                <TableCell sx={{ ...cellSx, fontWeight: 500 }}>{label}</TableCell>
                <TableCell sx={valueCellSx} align="right">
                  {portalValue}
                </TableCell>
                <TableCell sx={valueCellSx} align="right">
                  {bookValue}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
}

export function ReconciliationCaseDetailPage() {
  const { id } = useParams();
  const caseId = Number(id);
  const { can } = usePermissions();
  const canManage = can("cases.manage");
  const [tabIndex, setTabIndex] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const tab = RECORD_TABS[tabIndex];
  const categoryParam = tab?.key === "all" ? "" : tab?.category ? `?category=${tab.category}` : "";

  const caseQ = useQuery({
    queryKey: ["reconciliation-case", caseId],
    queryFn: () => apiFetch<CaseDetail>(`/app/reconciliation-cases/${caseId}`),
    enabled: Boolean(caseId),
  });

  const recordsQ = useQuery({
    queryKey: ["reconciliation-case-records", caseId, tab?.category],
    queryFn: () => apiFetch<CaseRecord[]>(`/app/reconciliation-cases/${caseId}/records${categoryParam}`),
    enabled: Boolean(caseId) && tab?.key !== "summary",
  });

  const summary = caseQ.data?.summary_counts ?? {};
  const summaryCards = useMemo(
    () => [
      { label: "Total GSTR-2B Records", value: summary.total_gstr2b_records ?? 0 },
      { label: "Total Purchase Register Records", value: summary.total_purchase_register_records ?? 0 },
      { label: "Matched with Books", value: summary.matched_with_books ?? 0 },
      { label: "Amount Mismatch", value: summary.amount_mismatch ?? 0 },
      { label: "Portal Open Items", value: summary.portal_open_items ?? 0 },
      { label: "Books Open Items", value: summary.books_open_items ?? 0 },
    ],
    [summary],
  );

  if (caseQ.isLoading) {
    return <Typography>Loading…</Typography>;
  }

  if (caseQ.isError || !caseQ.data) {
    return (
      <Alert severity="error">
        {caseQ.error instanceof ApiError ? caseQ.error.message : "Case not found"}
      </Alert>
    );
  }

  const c = caseQ.data;

  const handleExport = async () => {
    if (!tab) return;
    setExportError(null);
    setExporting(true);
    try {
      await exportCaseTabExcel(caseId, tab.key, c.case_name);
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "flex-start" }} mb={3} gap={2}>
        <Box>
          <Typography variant="h5" fontWeight={600}>
            {c.case_name}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" mt={1} flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              label={CASE_STATUS_LABELS[c.status] ?? c.status}
              color={CASE_STATUS_COLORS[c.status] ?? "default"}
            />
            <Typography variant="body2" color="text.secondary">
              {formatTaxPeriod(c.tax_period_month, c.tax_period_year)} ({formatTaxPeriodShort(c.tax_period_month, c.tax_period_year)})
            </Typography>
            {c.client_name && (
              <Typography variant="body2" color="text.secondary">
                · {c.client_name}
              </Typography>
            )}
          </Stack>
        </Box>
        {canManage && (
          <Button component={RouterLink} to={`/app/cases/${c.id}/edit`} startIcon={<EditOutlined />} variant="outlined">
            Edit Case
          </Button>
        )}
      </Stack>

      {c.error_message && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {c.error_message}
        </Alert>
      )}

      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">
                GSTR-2B File
              </Typography>
              <Typography variant="body2">{c.gstr2b_original_filename ?? "—"}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">
                Purchase Register File
              </Typography>
              <Typography variant="body2">{c.pr_original_filename ?? "—"}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">
                GSTR-2B Mapping
              </Typography>
              <Typography variant="body2">{c.gstr2b_mapping_name ?? "—"}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">
                Purchase Register Mapping
              </Typography>
              <Typography variant="body2">{c.pr_mapping_name ?? "—"}</Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {summaryCards.map((card) => (
          <Grid item xs={12} sm={6} md={4} key={card.label}>
            <SummaryCard {...card} />
          </Grid>
        ))}
      </Grid>

      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} sx={{ mb: 2 }} gap={1}>
        <Tabs value={tabIndex} onChange={(_, v) => setTabIndex(v)} sx={{ flex: 1 }}>
          {RECORD_TABS.map((t) => (
            <Tab key={t.key} label={t.label} />
          ))}
        </Tabs>
        <Button
          variant="outlined"
          size="small"
          startIcon={<FileDownloadOutlined />}
          onClick={handleExport}
          disabled={exporting || ["draft", "files_uploaded", "processing"].includes(c.status)}
          sx={{ flexShrink: 0, alignSelf: { xs: "flex-start", sm: "center" } }}
        >
          {exporting ? "Exporting…" : "Export to Excel"}
        </Button>
      </Stack>

      {exportError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setExportError(null)}>
          {exportError}
        </Alert>
      )}

      {tab?.key === "summary" ? (
        <Alert severity="info">Use the tabs above to browse processed records by reconciliation category.</Alert>
      ) : (
        <Card variant="outlined">
          <CardContent sx={{ p: 0, "&:last-child": { pb: 0 }, overflowX: "auto" }}>
            {recordsQ.isError && (
              <Alert severity="error" sx={{ m: 2 }}>
                {recordsQ.error instanceof ApiError ? recordsQ.error.message : "Failed to load records"}
              </Alert>
            )}
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" />
                  <TableCell>Category</TableCell>
                  <TableCell>Company GSTIN</TableCell>
                  <TableCell>Supplier Name</TableCell>
                  <TableCell>Supplier GSTIN</TableCell>
                  <TableCell>Invoice No</TableCell>
                  <TableCell>Invoice Date</TableCell>
                  <TableCell align="right">Taxable</TableCell>
                  <TableCell align="right">IGST</TableCell>
                  <TableCell align="right">SGST</TableCell>
                  <TableCell align="right">CGST</TableCell>
                  <TableCell align="right">Total Tax</TableCell>
                  <TableCell align="right">Grand Total</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Match Status</TableCell>
                  <TableCell>Remarks</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recordsQ.isLoading && (
                  <TableRow>
                    <TableCell colSpan={16}>Loading records…</TableCell>
                  </TableRow>
                )}
                {!recordsQ.isLoading && (recordsQ.data?.length ?? 0) === 0 && (
                  <TableRow>
                    <TableCell colSpan={16}>
                      <Typography color="text.secondary" py={2}>
                        No records in this category.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {recordsQ.data?.map((record) => (
                  <RecordRow key={record.id} record={record} />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
