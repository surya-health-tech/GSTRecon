import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import EditOutlined from "@mui/icons-material/EditOutlined";
import OpenInNewOutlined from "@mui/icons-material/OpenInNewOutlined";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import { usePermissions } from "../auth/usePermissions";
import {
  CASE_STATUS_COLORS,
  CASE_STATUS_LABELS,
  CASE_STATUS_OPTIONS,
  formatTaxPeriod,
  formatTaxPeriodShort,
} from "../lib/reconciliationCases";

type ReconciliationCase = {
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
  created_at: string;
  updated_at: string;
};

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function buildQueryParams(search: string, status: string, month: string, year: string) {
  const params = new URLSearchParams();
  if (search.trim()) params.set("search", search.trim());
  if (status) params.set("status_filter", status);
  if (month) params.set("tax_period_month", month);
  if (year) params.set("tax_period_year", year);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function ReconciliationCasesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = usePermissions();
  const canManage = can("cases.manage");

  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterMonth, setFilterMonth] = useState("");
  const [filterYear, setFilterYear] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ReconciliationCase | null>(null);

  const queryKey = useMemo(
    () => ["reconciliation-cases", search, filterStatus, filterMonth, filterYear],
    [search, filterStatus, filterMonth, filterYear],
  );

  const casesQ = useQuery({
    queryKey,
    queryFn: () =>
      apiFetch<ReconciliationCase[]>(
        `/app/reconciliation-cases${buildQueryParams(search, filterStatus, filterMonth, filterYear)}`,
      ),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/app/reconciliation-cases/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["reconciliation-cases"] });
    },
  });

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} mb={3} gap={2}>
        <Box>
          <Typography variant="h5" fontWeight={600}>
            Reconciliation Cases
          </Typography>
          <Typography color="text.secondary" mt={0.5}>
            Create and manage GSTR-2B vs Purchase Register reconciliation cases.
          </Typography>
        </Box>
        {canManage && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate("/app/cases/new")}>
            Create Case
          </Button>
        )}
      </Stack>

      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              label="Search"
              placeholder="Case name, client, or tax period month"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              size="small"
              fullWidth
            />
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Status</InputLabel>
              <Select label="Status" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                <MenuItem value="">All</MenuItem>
                {CASE_STATUS_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Tax Period Month"
              type="number"
              value={filterMonth}
              onChange={(e) => setFilterMonth(e.target.value)}
              size="small"
              inputProps={{ min: 1, max: 12 }}
              sx={{ minWidth: 160 }}
            />
            <TextField
              label="Tax Period Year"
              type="number"
              value={filterYear}
              onChange={(e) => setFilterYear(e.target.value)}
              size="small"
              sx={{ minWidth: 140 }}
            />
          </Stack>
        </CardContent>
      </Card>

      {casesQ.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {casesQ.error instanceof ApiError ? casesQ.error.message : "Failed to load cases"}
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Case Name</TableCell>
                <TableCell>Client Name</TableCell>
                <TableCell>Tax Period</TableCell>
                <TableCell>GSTR-2B File</TableCell>
                <TableCell>Purchase Register File</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Date Created</TableCell>
                <TableCell>Last Updated</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {casesQ.isLoading && (
                <TableRow>
                  <TableCell colSpan={9}>Loading…</TableCell>
                </TableRow>
              )}
              {!casesQ.isLoading && (casesQ.data?.length ?? 0) === 0 && (
                <TableRow>
                  <TableCell colSpan={9}>
                    <Typography color="text.secondary" py={2}>
                      No reconciliation cases yet.
                      {canManage && " Click Create Case to start a new reconciliation."}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {casesQ.data?.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell>{row.case_name}</TableCell>
                  <TableCell>{row.client_name ?? "—"}</TableCell>
                  <TableCell>
                    <Typography variant="body2">{formatTaxPeriod(row.tax_period_month, row.tax_period_year)}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatTaxPeriodShort(row.tax_period_month, row.tax_period_year)}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.gstr2b_original_filename ?? "—"}</TableCell>
                  <TableCell>{row.pr_original_filename ?? "—"}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={CASE_STATUS_LABELS[row.status] ?? row.status}
                      color={CASE_STATUS_COLORS[row.status] ?? "default"}
                    />
                  </TableCell>
                  <TableCell>{formatDate(row.created_at)}</TableCell>
                  <TableCell>{formatDate(row.updated_at)}</TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                      <IconButton
                        size="small"
                        component={RouterLink}
                        to={`/app/cases/${row.id}`}
                        title="View case"
                      >
                        <OpenInNewOutlined fontSize="small" />
                      </IconButton>
                      {canManage && (
                        <>
                          <IconButton
                            size="small"
                            component={RouterLink}
                            to={`/app/cases/${row.id}/edit`}
                            title="Edit case"
                          >
                            <EditOutlined fontSize="small" />
                          </IconButton>
                          <IconButton size="small" color="error" onClick={() => setDeleteTarget(row)} title="Delete case">
                            <DeleteOutline fontSize="small" />
                          </IconButton>
                        </>
                      )}
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete case?</DialogTitle>
        <DialogContent>
          <Typography>
            Delete <strong>{deleteTarget?.case_name}</strong>? This will remove uploaded files and processed results.
          </Typography>
          {deleteMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {deleteMutation.error instanceof ApiError ? deleteMutation.error.message : "Delete failed"}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
