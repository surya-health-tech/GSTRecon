import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import { usePermissions } from "../auth/usePermissions";

type PurchaseRegisterMapping = {
  id: number;
  mapping_name: string;
  source: string;
  original_filename: string | null;
  created_at: string;
  updated_at: string;
};

const SOURCE_OPTIONS = [
  { value: "zoho", label: "Zoho" },
  { value: "wings_erp", label: "Wings ERP" },
  { value: "erpnext", label: "ERPNext" },
  { value: "other", label: "Other" },
] as const;

const SOURCE_LABELS: Record<string, string> = Object.fromEntries(
  SOURCE_OPTIONS.map((s) => [s.value, s.label]),
);

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function buildQueryParams(search: string, source: string) {
  const params = new URLSearchParams();
  if (search.trim()) params.set("search", search.trim());
  if (source) params.set("source", source);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function PurchaseRegisterMappingsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = usePermissions();
  const canManage = can("data_mapping.manage");
  const [searchParams] = useSearchParams();

  const [search, setSearch] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<PurchaseRegisterMapping | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(
    searchParams.get("saved") === "1" ? "Purchase register mapping saved successfully." : null,
  );

  const queryKey = useMemo(() => ["purchase-register-mappings", search, filterSource], [search, filterSource]);

  const mappingsQ = useQuery({
    queryKey,
    queryFn: () =>
      apiFetch<PurchaseRegisterMapping[]>(
        `/app/data-mapping/purchase-register-mappings${buildQueryParams(search, filterSource)}`,
      ),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/app/data-mapping/purchase-register-mappings/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["purchase-register-mappings"] });
    },
  });

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} mb={3} gap={2}>
        <Box>
          <Typography variant="h5" fontWeight={600}>
            Purchase Register Mapping
          </Typography>
          <Typography color="text.secondary" mt={0.5}>
            Map purchase register Excel columns to reconciliation master fields.
          </Typography>
        </Box>
        {canManage && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => navigate("/app/data-mapping/purchase-register/new")}
          >
            Create Purchase Register Mapping
          </Button>
        )}
      </Stack>

      {successMsg && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              label="Search mappings"
              placeholder="Name or source"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              size="small"
              fullWidth
            />
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Source</InputLabel>
              <Select label="Source" value={filterSource} onChange={(e) => setFilterSource(e.target.value)}>
                <MenuItem value="">All</MenuItem>
                {SOURCE_OPTIONS.map((s) => (
                  <MenuItem key={s.value} value={s.value}>
                    {s.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </CardContent>
      </Card>

      {mappingsQ.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {mappingsQ.error instanceof ApiError
            ? mappingsQ.error.message
            : "Failed to load purchase register mappings"}
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Mapping Name</TableCell>
                <TableCell>Source</TableCell>
                <TableCell>Date Created</TableCell>
                <TableCell>Last Updated</TableCell>
                {canManage && <TableCell align="right">Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {(mappingsQ.data ?? []).map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.mapping_name}</TableCell>
                  <TableCell>{SOURCE_LABELS[row.source] ?? row.source}</TableCell>
                  <TableCell>{formatDate(row.created_at)}</TableCell>
                  <TableCell>{formatDate(row.updated_at)}</TableCell>
                  {canManage && (
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        aria-label="Edit"
                        component={RouterLink}
                        to={`/app/data-mapping/purchase-register/${row.id}/edit`}
                      >
                        <EditOutlined fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        aria-label="Delete"
                        color="error"
                        onClick={() => setDeleteTarget(row)}
                      >
                        <DeleteOutline fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {!mappingsQ.isLoading && (mappingsQ.data ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={canManage ? 5 : 4} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">No purchase register mappings match your filters.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={deleteTarget != null} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete mapping?</DialogTitle>
        <DialogContent>
          <Typography>
            Delete <strong>{deleteTarget?.mapping_name}</strong>? This cannot be undone.
          </Typography>
          {deleteMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {deleteMutation.error instanceof ApiError
                ? deleteMutation.error.message
                : "Could not delete mapping"}
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
