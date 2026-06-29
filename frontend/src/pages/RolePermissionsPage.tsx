import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Stack,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";

type RolePermissionsResponse = {
  roles: Record<string, Record<string, boolean>>;
  groups: Record<string, string[]>;
};

const ROLE_LABELS: Record<string, string> = {
  tenant_admin: "Admin",
  manager: "Manager",
  staff: "Staff",
};

const GROUP_LABELS: Record<string, string> = {
  reconciliation: "Reconciliation",
  clients: "Clients",
  data_mapping: "Data Mapping",
  team: "Team",
  settings: "Settings",
};

const PERM_LABEL_OVERRIDES: Record<string, string> = {
  "cases.access": "View Cases",
  "cases.manage": "Manage Cases",
  "notifications.view_my": "View My Notifications",
  "notifications.list_view": "View Notification List",
  "notifications.configure": "Configure Client Notifications",
  "settings.manage_reminders": "Manage Reminders",
};

function permLabel(key: string): string {
  if (PERM_LABEL_OVERRIDES[key]) return PERM_LABEL_OVERRIDES[key];
  const part = key.split(".").slice(1).join(" ");
  return part.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function RolePermissionsPage() {
  const { me } = useAuth();
  const isAdmin = me?.role === "tenant_admin";
  const { refreshMe } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["role-permissions"],
    queryFn: () => apiFetch<RolePermissionsResponse>("/app/role-permissions"),
    enabled: isAdmin,
  });

  const [draft, setDraft] = useState<Record<string, Record<string, boolean>> | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    if (q.data?.roles) setDraft(structuredClone(q.data.roles));
  }, [q.data?.roles]);

  const save = useMutation({
    mutationFn: () =>
      apiFetch<RolePermissionsResponse>("/app/role-permissions", {
        method: "PUT",
        body: JSON.stringify({ roles: draft }),
      }),
    onSuccess: async (data) => {
      setDraft(structuredClone(data.roles));
      setSavedMsg("Role permissions saved.");
      await qc.invalidateQueries({ queryKey: ["role-permissions"] });
      await refreshMe();
    },
    onError: () => setSavedMsg(null),
  });

  const roleOrder = useMemo(() => ["tenant_admin", "manager", "staff"], []);

  if (!isAdmin) {
    return (
      <Alert severity="warning">
        Only firm administrators can manage role permissions.
      </Alert>
    );
  }

  if (q.isLoading || !draft || !q.data) {
    return <Typography>Loading role permissions…</Typography>;
  }

  if (q.isError) {
    return (
      <Alert severity="error">
        {q.error instanceof ApiError ? q.error.message : "Could not load role permissions"}
      </Alert>
    );
  }

  const groups = q.data.groups;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={700}>
          Role permissions
        </Typography>
        <Typography color="text.secondary" sx={{ mt: 0.5 }}>
          Configure what each role can view and manage within your firm. Changes apply to all users with that role.
        </Typography>
        <Button component={RouterLink} to="/app/settings" size="small" sx={{ mt: 1 }}>
          Back to settings
        </Button>
      </Box>

      {savedMsg && (
        <Alert severity="success" onClose={() => setSavedMsg(null)}>
          {savedMsg}
        </Alert>
      )}
      {save.isError && (
        <Alert severity="error">
          {save.error instanceof ApiError ? save.error.message : "Save failed"}
        </Alert>
      )}

      {roleOrder.map((role) => (
        <Accordion key={role} defaultExpanded={role === "staff"}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography fontWeight={700}>{ROLE_LABELS[role] ?? role}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={2}>
              {Object.entries(groups).map(([groupKey, keys]) => (
                <Box key={groupKey}>
                  <Typography variant="subtitle2" fontWeight={700} gutterBottom>
                    {GROUP_LABELS[groupKey] ?? groupKey}
                  </Typography>
                  <Stack direction="row" flexWrap="wrap" useFlexGap sx={{ gap: 0 }}>
                    {keys.map((permKey) => (
                      <FormControlLabel
                        key={permKey}
                        control={
                          <Checkbox
                            size="small"
                            checked={Boolean(draft[role]?.[permKey])}
                            onChange={(e) => {
                              setDraft((prev) => {
                                if (!prev) return prev;
                                return {
                                  ...prev,
                                  [role]: { ...prev[role], [permKey]: e.target.checked },
                                };
                              });
                            }}
                          />
                        }
                        label={permLabel(permKey)}
                        sx={{ width: { xs: "100%", sm: "48%", md: "32%" }, mr: 0 }}
                      />
                    ))}
                  </Stack>
                </Box>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      ))}

      <Stack direction="row" spacing={2}>
        <Button
          variant="contained"
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          Save permissions
        </Button>
        <Button
          variant="outlined"
          onClick={() => q.data && setDraft(structuredClone(q.data.roles))}
          disabled={save.isPending}
        >
          Reset changes
        </Button>
      </Stack>
    </Stack>
  );
}
