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
  FormHelperText,
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
import { apiFetch, ApiError } from "../api/http";
import { usePermissions } from "../auth/usePermissions";
import { gstinValidationMessage, normalizeGstin } from "../lib/gstin";

type Client = {
  id: number;
  client_name: string;
  gst_number: string;
  purchase_system_type: string;
  created_at: string;
  updated_at: string;
};

type ClientForm = {
  client_name: string;
  gst_number: string;
  purchase_system_type: string;
};

const PURCHASE_SYSTEM_OPTIONS = [
  { value: "zoho", label: "Zoho" },
  { value: "wings_erp", label: "Wings ERP" },
  { value: "erpnext", label: "ERPNext" },
  { value: "tally", label: "Tally" },
  { value: "other", label: "Other" },
] as const;

const SYSTEM_LABELS: Record<string, string> = Object.fromEntries(
  PURCHASE_SYSTEM_OPTIONS.map((s) => [s.value, s.label]),
);

const EMPTY_FORM: ClientForm = {
  client_name: "",
  gst_number: "",
  purchase_system_type: "",
};

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function buildQueryParams(search: string, purchaseSystemType: string) {
  const params = new URLSearchParams();
  if (search.trim()) params.set("search", search.trim());
  if (purchaseSystemType) params.set("purchase_system_type", purchaseSystemType);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function ClientsPage() {
  const qc = useQueryClient();
  const { can } = usePermissions();
  const canManage = can("clients.manage");

  const [search, setSearch] = useState("");
  const [filterSystem, setFilterSystem] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Client | null>(null);
  const [form, setForm] = useState<ClientForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [gstError, setGstError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Client | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const queryKey = useMemo(() => ["clients", search, filterSystem], [search, filterSystem]);

  const clientsQ = useQuery({
    queryKey,
    queryFn: () => apiFetch<Client[]>(`/app/clients${buildQueryParams(search, filterSystem)}`),
  });

  const gstFieldError = gstError ?? (form.gst_number ? gstinValidationMessage(form.gst_number) : null);
  const formValid =
    form.client_name.trim().length > 0 &&
    form.purchase_system_type.length > 0 &&
    !gstinValidationMessage(form.gst_number);

  const closeDialog = () => {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setGstError(null);
  };

  const openAdd = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setGstError(null);
    setDialogOpen(true);
  };

  const openEdit = (row: Client) => {
    setEditing(row);
    setForm({
      client_name: row.client_name,
      gst_number: row.gst_number,
      purchase_system_type: row.purchase_system_type,
    });
    setFormError(null);
    setGstError(null);
    setDialogOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        client_name: form.client_name.trim(),
        gst_number: normalizeGstin(form.gst_number),
        purchase_system_type: form.purchase_system_type,
      };
      if (editing) {
        return apiFetch<Client>(`/app/clients/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }
      return apiFetch<Client>("/app/clients", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["clients"] });
      setSuccessMsg(editing ? "Client updated successfully." : "Client added successfully.");
      closeDialog();
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Could not save client");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/app/clients/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleteTarget(null);
      setSuccessMsg("Client deleted successfully.");
      void qc.invalidateQueries({ queryKey: ["clients"] });
    },
  });

  const isEmpty = !clientsQ.isLoading && (clientsQ.data ?? []).length === 0 && !search && !filterSystem;

  return (
    <Box>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ sm: "center" }}
        mb={3}
        gap={2}
      >
        <Box>
          <Typography variant="h5" fontWeight={600}>
            Clients
          </Typography>
          <Typography color="text.secondary" mt={0.5}>
            Manage clients for GSTR-2B reconciliation.
          </Typography>
        </Box>
        {canManage && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
            Add Client
          </Button>
        )}
      </Stack>

      {successMsg && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {!isEmpty && (
        <Card variant="outlined" sx={{ mb: 2 }}>
          <CardContent>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField
                label="Search clients"
                placeholder="Client name or GST number"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                size="small"
                fullWidth
              />
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Purchase System Type</InputLabel>
                <Select
                  label="Purchase System Type"
                  value={filterSystem}
                  onChange={(e) => setFilterSystem(e.target.value)}
                >
                  <MenuItem value="">All</MenuItem>
                  {PURCHASE_SYSTEM_OPTIONS.map((s) => (
                    <MenuItem key={s.value} value={s.value}>
                      {s.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
          </CardContent>
        </Card>
      )}

      {clientsQ.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {clientsQ.error instanceof ApiError ? clientsQ.error.message : "Failed to load clients"}
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Client Name</TableCell>
                <TableCell>GST Number</TableCell>
                <TableCell>Purchase System Type</TableCell>
                <TableCell>Date Created</TableCell>
                <TableCell>Last Updated</TableCell>
                {canManage && <TableCell align="right">Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {(clientsQ.data ?? []).map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.client_name}</TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {row.gst_number}
                    </Typography>
                  </TableCell>
                  <TableCell>{SYSTEM_LABELS[row.purchase_system_type] ?? row.purchase_system_type}</TableCell>
                  <TableCell>{formatDate(row.created_at)}</TableCell>
                  <TableCell>{formatDate(row.updated_at)}</TableCell>
                  {canManage && (
                    <TableCell align="right">
                      <IconButton size="small" aria-label="Edit" onClick={() => openEdit(row)}>
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
              {!clientsQ.isLoading && (clientsQ.data ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={canManage ? 6 : 5} align="center" sx={{ py: 6 }}>
                    <Stack spacing={2} alignItems="center">
                      <Typography color="text.secondary">
                        {search || filterSystem
                          ? "No clients match your search or filters."
                          : "No clients added yet."}
                      </Typography>
                      {canManage && !search && !filterSystem && (
                        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
                          Add Client
                        </Button>
                      )}
                    </Stack>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onClose={closeDialog} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? "Edit Client" : "Add Client"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Client Name"
              value={form.client_name}
              onChange={(e) => {
                setForm((f) => ({ ...f, client_name: e.target.value }));
                setFormError(null);
              }}
              required
              fullWidth
            />
            <TextField
              label="GST Number"
              value={form.gst_number}
              onChange={(e) => {
                setForm((f) => ({ ...f, gst_number: e.target.value.toUpperCase() }));
                setGstError(null);
                setFormError(null);
              }}
              required
              fullWidth
              inputProps={{ maxLength: 15, style: { fontFamily: "monospace" } }}
              error={Boolean(gstFieldError)}
              helperText={gstFieldError ?? "15-character GSTIN (e.g. 33ABACS9688N1ZI)"}
            />
            <FormControl fullWidth required error={!form.purchase_system_type && Boolean(formError)}>
              <InputLabel>Purchase System Type</InputLabel>
              <Select
                label="Purchase System Type"
                value={form.purchase_system_type}
                onChange={(e) => {
                  setForm((f) => ({ ...f, purchase_system_type: e.target.value }));
                  setFormError(null);
                }}
              >
                {PURCHASE_SYSTEM_OPTIONS.map((s) => (
                  <MenuItem key={s.value} value={s.value}>
                    {s.label}
                  </MenuItem>
                ))}
              </Select>
              {!form.purchase_system_type && formError && (
                <FormHelperText>Purchase System Type is required</FormHelperText>
              )}
            </FormControl>
            {formError && <Alert severity="error">{formError}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!formValid || saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteTarget != null} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete client?</DialogTitle>
        <DialogContent>
          <Typography>
            Delete client <strong>{deleteTarget?.client_name}</strong> ({deleteTarget?.gst_number})? This cannot be
            undone.
          </Typography>
          {deleteMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {deleteMutation.error instanceof ApiError ? deleteMutation.error.message : "Could not delete client"}
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
