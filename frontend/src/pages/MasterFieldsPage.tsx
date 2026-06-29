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
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
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
import { fieldNameToCode } from "../lib/fieldCode";

type MasterField = {
  id: number;
  field_name: string;
  field_code: string;
  data_type: string;
  is_required: boolean;
  applicable_source: string;
  is_system: boolean;
  is_active: boolean;
  display_order: number;
};

type FieldForm = {
  field_name: string;
  field_code: string;
  data_type: string;
  is_required: boolean;
  applicable_source: string;
  is_active: boolean;
  display_order: number;
};

const DATA_TYPES = ["text", "decimal", "date", "number", "boolean"] as const;
const APPLICABLE_SOURCES = [
  { value: "gstr_2b", label: "GSTR-2B" },
  { value: "purchase_register", label: "Purchase Register" },
  { value: "both", label: "Both" },
] as const;

const DATA_TYPE_LABELS: Record<string, string> = {
  text: "Text",
  decimal: "Decimal",
  date: "Date",
  number: "Number",
  boolean: "Boolean",
};

const SOURCE_LABELS: Record<string, string> = {
  gstr_2b: "GSTR-2B",
  purchase_register: "Purchase Register",
  both: "Both",
};

const EMPTY_FORM: FieldForm = {
  field_name: "",
  field_code: "",
  data_type: "text",
  is_required: true,
  applicable_source: "both",
  is_active: true,
  display_order: 0,
};

function buildQueryParams(filters: {
  search: string;
  applicable_source: string;
  data_type: string;
  is_required: string;
  is_active: string;
  field_kind: string;
}) {
  const params = new URLSearchParams();
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.applicable_source) params.set("applicable_source", filters.applicable_source);
  if (filters.data_type) params.set("data_type", filters.data_type);
  if (filters.is_required !== "") params.set("is_required", filters.is_required);
  if (filters.is_active !== "") params.set("is_active", filters.is_active);
  if (filters.field_kind === "system") params.set("is_system", "true");
  if (filters.field_kind === "custom") params.set("is_system", "false");
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function MasterFieldsPage() {
  const qc = useQueryClient();
  const { can } = usePermissions();
  const canManage = can("data_mapping.manage");

  const [search, setSearch] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterDataType, setFilterDataType] = useState("");
  const [filterRequired, setFilterRequired] = useState("");
  const [filterActive, setFilterActive] = useState("");
  const [filterKind, setFilterKind] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<MasterField | null>(null);
  const [form, setForm] = useState<FieldForm>(EMPTY_FORM);
  const [codeTouched, setCodeTouched] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<MasterField | null>(null);

  const queryKey = useMemo(
    () => [
      "master-fields",
      search,
      filterSource,
      filterDataType,
      filterRequired,
      filterActive,
      filterKind,
    ],
    [search, filterSource, filterDataType, filterRequired, filterActive, filterKind]
  );

  const fieldsQ = useQuery({
    queryKey,
    queryFn: () =>
      apiFetch<MasterField[]>(
        `/app/data-mapping/master-fields${buildQueryParams({
          search,
          applicable_source: filterSource,
          data_type: filterDataType,
          is_required: filterRequired,
          is_active: filterActive,
          field_kind: filterKind,
        })}`
      ),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        field_name: form.field_name.trim(),
        field_code: form.field_code.trim().toLowerCase(),
        data_type: form.data_type,
        is_required: form.is_required,
        applicable_source: form.applicable_source,
        is_active: form.is_active,
        display_order: form.display_order,
      };
      if (editing) {
        if (editing.is_system) {
          return apiFetch<MasterField>(`/app/data-mapping/master-fields/${editing.id}`, {
            method: "PATCH",
            body: JSON.stringify({
              display_order: payload.display_order,
              is_active: payload.is_active,
            }),
          });
        }
        return apiFetch<MasterField>(`/app/data-mapping/master-fields/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }
      return apiFetch<MasterField>("/app/data-mapping/master-fields", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["master-fields"] });
      closeDialog();
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Could not save field");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/app/data-mapping/master-fields/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["master-fields"] });
      setDeleteTarget(null);
    },
  });

  const openAdd = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setCodeTouched(false);
    setFormError(null);
    setDialogOpen(true);
  };

  const openEdit = (row: MasterField) => {
    setEditing(row);
    setForm({
      field_name: row.field_name,
      field_code: row.field_code,
      data_type: row.data_type,
      is_required: row.is_required,
      applicable_source: row.applicable_source,
      is_active: row.is_active,
      display_order: row.display_order,
    });
    setCodeTouched(true);
    setFormError(null);
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    saveMutation.reset();
  };

  const onNameChange = (name: string) => {
    setForm((f) => ({
      ...f,
      field_name: name,
      field_code: !codeTouched && !editing?.is_system ? fieldNameToCode(name) : f.field_code,
    }));
  };

  const formValid =
    form.field_name.trim().length > 0 &&
    form.field_code.trim().length > 0 &&
    form.data_type.length > 0 &&
    form.applicable_source.length > 0 &&
    form.display_order >= 0;

  const isSystemEdit = Boolean(editing?.is_system);

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={2} gap={2}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            Master Fields
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Define the standard fields used when mapping GSTR-2B portal data and purchase register exports.
          </Typography>
        </Box>
        {canManage && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
            Add Field
          </Button>
        )}
      </Stack>

      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} flexWrap="wrap">
            <TextField
              label="Search"
              size="small"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Field name or code"
              sx={{ minWidth: 200, flex: 1 }}
            />
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>Applicable Source</InputLabel>
              <Select
                label="Applicable Source"
                value={filterSource}
                onChange={(e) => setFilterSource(e.target.value)}
              >
                <MenuItem value="">All</MenuItem>
                {APPLICABLE_SOURCES.map((s) => (
                  <MenuItem key={s.value} value={s.value}>
                    {s.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 130 }}>
              <InputLabel>Data Type</InputLabel>
              <Select label="Data Type" value={filterDataType} onChange={(e) => setFilterDataType(e.target.value)}>
                <MenuItem value="">All</MenuItem>
                {DATA_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>
                    {DATA_TYPE_LABELS[t]}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Required</InputLabel>
              <Select label="Required" value={filterRequired} onChange={(e) => setFilterRequired(e.target.value)}>
                <MenuItem value="">All</MenuItem>
                <MenuItem value="true">Required</MenuItem>
                <MenuItem value="false">Optional</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Active</InputLabel>
              <Select label="Active" value={filterActive} onChange={(e) => setFilterActive(e.target.value)}>
                <MenuItem value="">All</MenuItem>
                <MenuItem value="true">Active</MenuItem>
                <MenuItem value="false">Inactive</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Field Kind</InputLabel>
              <Select label="Field Kind" value={filterKind} onChange={(e) => setFilterKind(e.target.value)}>
                <MenuItem value="">All</MenuItem>
                <MenuItem value="system">System</MenuItem>
                <MenuItem value="custom">Custom</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </CardContent>
      </Card>

      {fieldsQ.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {fieldsQ.error instanceof ApiError ? fieldsQ.error.message : "Failed to load master fields"}
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Display Order</TableCell>
                <TableCell>Field Name</TableCell>
                <TableCell>Field Code</TableCell>
                <TableCell>Data Type</TableCell>
                <TableCell>Required</TableCell>
                <TableCell>Applicable Source</TableCell>
                <TableCell>Kind</TableCell>
                <TableCell>Active</TableCell>
                {canManage && <TableCell align="right">Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {(fieldsQ.data ?? []).map((row) => (
                <TableRow
                  key={row.id}
                  sx={{ opacity: row.is_active ? 1 : 0.55, bgcolor: row.is_active ? undefined : "action.hover" }}
                >
                  <TableCell>{row.display_order}</TableCell>
                  <TableCell>{row.field_name}</TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {row.field_code}
                    </Typography>
                  </TableCell>
                  <TableCell>{DATA_TYPE_LABELS[row.data_type] ?? row.data_type}</TableCell>
                  <TableCell>{row.is_required ? "Required" : "Optional"}</TableCell>
                  <TableCell>{SOURCE_LABELS[row.applicable_source] ?? row.applicable_source}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={row.is_system ? "System" : "Custom"}
                      color={row.is_system ? "default" : "primary"}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={row.is_active ? "Active" : "Inactive"}
                      color={row.is_active ? "success" : "default"}
                      variant="outlined"
                    />
                  </TableCell>
                  {canManage && (
                    <TableCell align="right">
                      <IconButton size="small" aria-label="Edit" onClick={() => openEdit(row)}>
                        <EditOutlined fontSize="small" />
                      </IconButton>
                      {!row.is_system && (
                        <IconButton
                          size="small"
                          aria-label="Delete"
                          color="error"
                          onClick={() => setDeleteTarget(row)}
                        >
                          <DeleteOutline fontSize="small" />
                        </IconButton>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {!fieldsQ.isLoading && (fieldsQ.data ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={canManage ? 9 : 8} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">No master fields match your filters.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onClose={closeDialog} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? "Edit Master Field" : "Add Master Field"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {isSystemEdit && (
              <Alert severity="info">
                This is a system field. You can change display order and active status only. Field code cannot be
                changed.
              </Alert>
            )}
            {!isSystemEdit && (
              <>
                <TextField
                  label="Field Name"
                  value={form.field_name}
                  onChange={(e) => onNameChange(e.target.value)}
                  required
                  fullWidth
                />
                <TextField
                  label="Field Code"
                  value={form.field_code}
                  onChange={(e) => {
                    setCodeTouched(true);
                    setForm((f) => ({ ...f, field_code: e.target.value }));
                  }}
                  required
                  fullWidth
                  helperText="snake_case key used in mappings"
                  inputProps={{ style: { fontFamily: "monospace" } }}
                />
                <FormControl fullWidth required>
                  <InputLabel>Data Type</InputLabel>
                  <Select
                    label="Data Type"
                    value={form.data_type}
                    onChange={(e) => setForm((f) => ({ ...f, data_type: e.target.value }))}
                  >
                    {DATA_TYPES.map((t) => (
                      <MenuItem key={t} value={t}>
                        {DATA_TYPE_LABELS[t]}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl fullWidth required>
                  <InputLabel>Applicable Source</InputLabel>
                  <Select
                    label="Applicable Source"
                    value={form.applicable_source}
                    onChange={(e) => setForm((f) => ({ ...f, applicable_source: e.target.value }))}
                  >
                    {APPLICABLE_SOURCES.map((s) => (
                      <MenuItem key={s.value} value={s.value}>
                        {s.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControlLabel
                  control={
                    <Switch
                      checked={form.is_required}
                      onChange={(e) => setForm((f) => ({ ...f, is_required: e.target.checked }))}
                    />
                  }
                  label="Required field"
                />
              </>
            )}
            <TextField
              label="Display Order"
              type="number"
              value={form.display_order}
              onChange={(e) =>
                setForm((f) => ({ ...f, display_order: Math.max(0, Number(e.target.value) || 0) }))
              }
              required
              fullWidth
              inputProps={{ min: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                />
              }
              label="Active"
            />
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
        <DialogTitle>Delete master field?</DialogTitle>
        <DialogContent>
          <Typography>
            Delete <strong>{deleteTarget?.field_name}</strong>? This cannot be undone.
          </Typography>
          {deleteMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {deleteMutation.error instanceof ApiError
                ? deleteMutation.error.message
                : "Could not delete field"}
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
