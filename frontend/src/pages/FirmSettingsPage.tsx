import {
  Alert,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import {
  DEFAULT_FIRM_TIMEZONE,
  normalizeFirmTimezone,
  TIMEZONE_OPTIONS,
  timezoneLabel,
} from "../lib/timezones";

type FirmTenant = {
  id: number;
  name: string;
  slug: string;
  status: string;
  legal_name: string | null;
  timezone: string;
  plan_key: string;
  max_users: number;
  max_clients: number;
  storage_limit_mb: number;
  max_email_accounts: number;
};

export function FirmSettingsPage() {
  const { me, refreshMe } = useAuth();
  const isAdmin = me?.role === "tenant_admin";
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: ["firm-tenant"],
    queryFn: () => apiFetch<FirmTenant>("/app/tenant"),
  });

  const [name, setName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [timezone, setTimezone] = useState(DEFAULT_FIRM_TIMEZONE);

  useEffect(() => {
    if (q.data) {
      setName(q.data.name);
      setLegalName(q.data.legal_name ?? "");
      setTimezone(normalizeFirmTimezone(q.data.timezone));
    }
  }, [q.data]);

  const save = useMutation({
    mutationFn: () =>
      apiFetch<FirmTenant>("/app/tenant", {
        method: "PATCH",
        body: JSON.stringify({
          name,
          legal_name: legalName.trim() ? legalName.trim() : null,
          timezone,
        }),
      }),
    onSuccess: async () => {
      void qc.invalidateQueries({ queryKey: ["firm-tenant"] });
      void qc.invalidateQueries({ queryKey: ["firm-dashboard"] });
      await refreshMe();
    },
  });

  if (q.isLoading) return <Typography>Loading firm profile…</Typography>;
  if (q.isError) {
    return (
      <Alert severity="error">
        {q.error instanceof ApiError ? q.error.message : "Could not load settings"}
      </Alert>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4" fontWeight={700}>
        Firm Profile
      </Typography>
      <Typography color="text.secondary">
        Profile details for your practice. Plan limits are managed by the platform operator.
      </Typography>

      <Card variant="outlined">
        <CardContent>
          <Stack spacing={2} maxWidth={560}>
            {!isAdmin && (
              <Alert severity="info">Only firm administrators can edit these fields.</Alert>
            )}
            <TextField label="Firm name" value={name} onChange={(e) => setName(e.target.value)} fullWidth disabled={!isAdmin} />
            <TextField
              label="Legal business name"
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
              fullWidth
              disabled={!isAdmin}
              helperText="Optional; shown on documents and the client portal later."
            />
            <FormControl fullWidth size="small" disabled={!isAdmin}>
              <InputLabel id="firm-timezone-label">Timezone (IANA)</InputLabel>
              <Select
                labelId="firm-timezone-label"
                label="Timezone (IANA)"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
              >
                {TIMEZONE_OPTIONS.map((tz) => (
                  <MenuItem key={tz} value={tz}>
                    {timezoneLabel(tz)}
                  </MenuItem>
                ))}
                {timezone && !(TIMEZONE_OPTIONS as readonly string[]).includes(timezone) && (
                  <MenuItem value={timezone}>{timezoneLabel(timezone)}</MenuItem>
                )}
              </Select>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: "block" }}>
                Used for task time logging, reminders, work due filters, and dashboard date ranges.
              </Typography>
            </FormControl>
            {save.isError && (
              <Alert severity="error">
                {save.error instanceof ApiError ? save.error.message : "Save failed"}
              </Alert>
            )}
            {save.isSuccess && <Alert severity="success">Saved.</Alert>}
            {isAdmin && (
              <Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? "Saving…" : "Save changes"}
              </Button>
            )}
          </Stack>
        </CardContent>
      </Card>

      {q.data && (
        <Card variant="outlined">
          <CardContent>
            <Typography fontWeight={600} gutterBottom>
              Plan & limits
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Plan: {q.data.plan_key} · Users up to {q.data.max_users} · Clients up to {q.data.max_clients} · Storage{" "}
              {q.data.storage_limit_mb} MB · Email mailboxes {q.data.max_email_accounts}
            </Typography>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
}
