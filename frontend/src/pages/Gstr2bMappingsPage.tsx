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
  IconButton,
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
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import EditOutlined from "@mui/icons-material/EditOutlined";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import { usePermissions } from "../auth/usePermissions";

type Gstr2bMapping = {
  id: number;
  mapping_name: string;
  version: string;
  is_active: boolean;
  original_filename: string | null;
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

function buildQueryParams(search: string) {
  const params = new URLSearchParams();
  if (search.trim()) params.set("search", search.trim());
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function Gstr2bMappingsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = usePermissions();
  const canManage = can("data_mapping.manage");
  const [searchParams] = useSearchParams();

  const [search, setSearch] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Gstr2bMapping | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(
    searchParams.get("saved") === "1" ? "GSTR-2B mapping saved successfully." : null,
  );

  const queryKey = useMemo(() => ["gstr2b-mappings", search], [search]);

  const mappingsQ = useQuery({
    queryKey,
    queryFn: () => apiFetch<Gstr2bMapping[]>(`/app/data-mapping/gstr-2b-mappings${buildQueryParams(search)}`),
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch<Gstr2bMapping>(`/app/data-mapping/gstr-2b-mappings/${id}/activate`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["gstr2b-mappings"] });
      setSuccessMsg("Active GSTR-2B mapping version updated.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/app/data-mapping/gstr-2b-mappings/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["gstr2b-mappings"] });
    },
  });

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} mb={3} gap={2}>
        <Box>
          <Typography variant="h5" fontWeight={600}>
            GSTR-2B Mapping
          </Typography>
          <Typography color="text.secondary" mt={0.5}>
            Manage GSTR-2B column mapping versions for GST portal Excel imports.
          </Typography>
        </Box>
        {canManage && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate("/app/data-mapping/gstr-2b/new")}>
            Create GSTR-2B Mapping
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
          <TextField
            label="Search mappings"
            placeholder="Name or version"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            size="small"
            fullWidth
          />
        </CardContent>
      </Card>

      {mappingsQ.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {mappingsQ.error instanceof ApiError ? mappingsQ.error.message : "Failed to load GSTR-2B mappings"}
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Mapping Name</TableCell>
                <TableCell>Version</TableCell>
                <TableCell>Date Created</TableCell>
                <TableCell>Last Updated</TableCell>
                <TableCell>Active Status</TableCell>
                {canManage && <TableCell align="right">Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {(mappingsQ.data ?? []).map((row) => (
                <TableRow key={row.id} sx={{ bgcolor: row.is_active ? "rgba(46, 125, 50, 0.04)" : undefined }}>
                  <TableCell>{row.mapping_name}</TableCell>
                  <TableCell>{row.version}</TableCell>
                  <TableCell>{formatDate(row.created_at)}</TableCell>
                  <TableCell>{formatDate(row.updated_at)}</TableCell>
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
                      <IconButton
                        size="small"
                        aria-label="View or Edit"
                        component={RouterLink}
                        to={`/app/data-mapping/gstr-2b/${row.id}/edit`}
                      >
                        <EditOutlined fontSize="small" />
                      </IconButton>
                      {!row.is_active && (
                        <IconButton
                          size="small"
                          aria-label="Mark as Active"
                          color="success"
                          disabled={activateMutation.isPending}
                          onClick={() => activateMutation.mutate(row.id)}
                        >
                          <CheckCircleOutline fontSize="small" />
                        </IconButton>
                      )}
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
                  <TableCell colSpan={canManage ? 6 : 5} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">No GSTR-2B mappings match your search.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={deleteTarget != null} onClose={() => setDeleteTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Delete mapping version?</DialogTitle>
        <DialogContent>
          {deleteTarget?.is_active ? (
            <Alert severity="warning" sx={{ mb: 2 }}>
              This is the active mapping version. Mark another version as active before deleting it.
            </Alert>
          ) : null}
          <Typography>
            Delete <strong>{deleteTarget?.mapping_name}</strong> (version {deleteTarget?.version})? This cannot be
            undone.
          </Typography>
          {deleteMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {deleteMutation.error instanceof ApiError ? deleteMutation.error.message : "Could not delete mapping"}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending || deleteTarget?.is_active}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
