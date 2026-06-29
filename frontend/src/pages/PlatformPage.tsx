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
  Divider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiFetch, ApiError } from "../api/http";

type Tenant = {
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

type InviteResult = {
  invitation_id: number;
  email: string;
  expires_at: string;
  invite_token: string;
  invite_url: string;
  email_sent: boolean;
  email_error: string | null;
  resent?: boolean;
};

type PlatformEmailStatus = {
  configured: boolean;
  delivery: string | null;
  provider: string | null;
  from_address: string | null;
  from_name: string | null;
  oauth_available: boolean;
};

type OAuthHealth = {
  google: { configured: boolean; missing_fields: string[] };
  microsoft365: { configured: boolean; missing_fields: string[] };
};

function statusColor(status: string): "default" | "success" | "warning" | "error" {
  if (status === "active") return "success";
  if (status === "trial") return "warning";
  if (status === "suspended" || status === "cancelled") return "error";
  return "default";
}

function providerLabel(provider: string | null): string {
  if (provider === "gmail") return "Gmail";
  if (provider === "microsoft365") return "Microsoft 365";
  if (provider === "smtp") return "SMTP";
  return provider ?? "—";
}

export function PlatformPage() {
  const qc = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const { startTenantPortal, startingTenantPortal } = useAuth();

  const tenantsQ = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: () => apiFetch<Tenant[]>("/platform/tenants"),
  });

  const emailStatusQ = useQuery({
    queryKey: ["platform-email-status"],
    queryFn: () => apiFetch<PlatformEmailStatus>("/platform/email-status"),
  });

  const oauthHealthQ = useQuery({
    queryKey: ["platform-email-oauth-health"],
    queryFn: () => apiFetch<OAuthHealth>("/platform/email/oauth/health"),
    enabled: emailStatusQ.data?.oauth_available ?? false,
  });

  const oauthResult = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const oauthStatus = oauthResult.get("oauth");
  const oauthMessage = oauthResult.get("message");
  const oauthProvider = oauthResult.get("provider");

  const startOAuth = useMutation({
    mutationFn: (provider: "gmail" | "microsoft365") =>
      apiFetch<{ auth_url: string }>(`/platform/email/oauth/start?provider=${provider}`),
    onSuccess: (res) => {
      window.location.href = res.auth_url;
    },
  });

  const disconnectOAuth = useMutation({
    mutationFn: () => apiFetch("/platform/email/oauth", { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["platform-email-status"] }),
  });

  const [name, setName] = useState("Brightview CPA Group");
  const [slug, setSlug] = useState("brightview-cpa");
  const [createError, setCreateError] = useState<string | null>(null);

  const createTenant = useMutation({
    mutationFn: () =>
      apiFetch<Tenant>("/platform/tenants", {
        method: "POST",
        body: JSON.stringify({ name, slug }),
      }),
    onSuccess: () => {
      setCreateError(null);
      void qc.invalidateQueries({ queryKey: ["platform-tenants"] });
    },
    onError: (err) => {
      setCreateError(err instanceof ApiError ? err.message : "Create failed");
    },
  });

  const patchTenant = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      apiFetch<Tenant>(`/platform/tenants/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["platform-tenants"] }),
  });

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTenantId, setDeleteTenantId] = useState<number | null>(null);
  const [deleteTargetSlug, setDeleteTargetSlug] = useState<string>("");
  const [deleteConfirm, setDeleteConfirm] = useState("");

  const deleteTenant = useMutation({
    mutationFn: () => {
      if (deleteTenantId == null) throw new Error("Missing tenant id");
      const slug = (deleteConfirm || "").trim();
      return apiFetch<void>(`/platform/tenants/${deleteTenantId}?confirm_slug=${encodeURIComponent(slug)}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      setDeleteOpen(false);
      setDeleteTenantId(null);
      setDeleteTargetSlug("");
      setDeleteConfirm("");
      void qc.invalidateQueries({ queryKey: ["platform-tenants"] });
    },
  });

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteTenantId, setInviteTenantId] = useState<number | null>(null);
  const [inviteEmail, setInviteEmail] = useState("sarah.mitchell@brightviewcpa.com");
  const [inviteName, setInviteName] = useState("Sarah Mitchell");
  const [createdInvite, setCreatedInvite] = useState<InviteResult | null>(null);
  const invite = useMutation({
    mutationFn: () =>
      apiFetch<InviteResult>(`/platform/tenants/${inviteTenantId}/invitations`, {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail,
          full_name: inviteName,
          role: "tenant_admin",
        }),
      }),
    onSuccess: (data) => setCreatedInvite(data),
  });
  const resendInvite = useMutation({
    mutationFn: () =>
      apiFetch<InviteResult>(
        `/platform/tenants/${inviteTenantId}/invitations/${createdInvite!.invitation_id}/resend`,
        { method: "POST" }
      ),
    onSuccess: (data) => setCreatedInvite(data),
  });

  const email = emailStatusQ.data;
  const oauthConnected = email?.delivery === "oauth";

  return (
    <Stack spacing={3}>
      <Typography variant="h4" fontWeight={700}>
        Platform · Tenants
      </Typography>
      <Typography color="text.secondary">
        Create a tenant, set lifecycle and limits, then invite the first firm admin. Invites are sent from your
        connected mailbox (OAuth) or platform SMTP when configured.
      </Typography>

      {oauthStatus === "success" && (
        <Alert severity="success" onClose={() => navigate("/platform", { replace: true })}>
          {providerLabel(oauthProvider)} connected for platform invites.
        </Alert>
      )}
      {oauthStatus === "error" && (
        <Alert severity="error" onClose={() => navigate("/platform", { replace: true })}>
          OAuth connect failed{oauthMessage ? `: ${oauthMessage}` : ""}.
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent>
          <Typography fontWeight={600} gutterBottom>
            Platform email (tenant invites)
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Connect Gmail or Microsoft 365 to send firm-admin invites without an app password. OAuth uses Mail.Send /
            gmail.send only — separate from firm email sync (IMAP).
          </Typography>

          {emailStatusQ.isLoading && <Typography>Checking email setup…</Typography>}
          {email && !email.configured && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Platform email is not configured. Connect a mailbox below, or set PLATFORM_SMTP_HOST and
              PLATFORM_EMAIL_FROM in the backend environment.
            </Alert>
          )}
          {email?.configured && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Invites send via {email.delivery === "oauth" ? "OAuth" : "SMTP"} ({providerLabel(email.provider)}) from{" "}
              {email.from_address}
              {email.from_name ? ` (${email.from_name})` : ""}.
            </Alert>
          )}

          {email?.oauth_available && (
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} flexWrap="wrap" useFlexGap>
              <Button
                variant="outlined"
                onClick={() => startOAuth.mutate("gmail")}
                disabled={startOAuth.isPending || !oauthHealthQ.data?.google.configured}
              >
                Connect Gmail
              </Button>
              <Button
                variant="outlined"
                onClick={() => startOAuth.mutate("microsoft365")}
                disabled={startOAuth.isPending || !oauthHealthQ.data?.microsoft365.configured}
              >
                Connect Microsoft 365
              </Button>
              {oauthConnected && (
                <Button
                  variant="outlined"
                  color="warning"
                  onClick={() => disconnectOAuth.mutate()}
                  disabled={disconnectOAuth.isPending}
                >
                  Disconnect OAuth
                </Button>
              )}
            </Stack>
          )}

          {oauthHealthQ.data && !oauthHealthQ.data.google.configured && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              Gmail OAuth env: {oauthHealthQ.data.google.missing_fields.join(", ") || "ok"}
            </Typography>
          )}
          {startOAuth.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {startOAuth.error instanceof ApiError ? startOAuth.error.message : "Could not start OAuth"}
            </Alert>
          )}
        </CardContent>
      </Card>

      <Card variant="outlined">
        <CardContent>
          <Typography fontWeight={600} gutterBottom>
            Create tenant
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="flex-start">
            <TextField label="Firm name" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
            <TextField
              label="Slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase())}
              fullWidth
              helperText="Lowercase letters, numbers, and hyphens"
            />
            <Button
              variant="contained"
              onClick={() => createTenant.mutate()}
              disabled={createTenant.isPending}
              sx={{ mt: { xs: 0, sm: 1 } }}
            >
              Create
            </Button>
          </Stack>
          {createError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {createError}
            </Alert>
          )}
        </CardContent>
      </Card>

      <Card variant="outlined">
        <CardContent>
          <Typography fontWeight={600} gutterBottom>
            Tenants
          </Typography>
          {tenantsQ.isLoading && <Typography>Loading…</Typography>}
          {tenantsQ.isError && (
            <Alert severity="error">
              {tenantsQ.error instanceof ApiError ? tenantsQ.error.message : "Failed to load"}
            </Alert>
          )}
          {patchTenant.isError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {patchTenant.error instanceof ApiError ? patchTenant.error.message : "Update failed"}
            </Alert>
          )}
          <Stack divider={<Divider flexItem />} spacing={2}>
            {(tenantsQ.data ?? []).map((t) => (
              <Box key={t.id} display="flex" alignItems="flex-start" gap={2} flexWrap="wrap">
                <Box flex={1} minWidth={240}>
                  <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
                    <Typography fontWeight={600}>{t.name}</Typography>
                    <Chip size="small" label={t.status} color={statusColor(t.status)} />
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {t.slug} · plan {t.plan_key} · users ≤ {t.max_users} · clients ≤ {t.max_clients} ·{" "}
                    {t.storage_limit_mb} MB storage
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={patchTenant.isPending || t.status === "active"}
                    onClick={() => patchTenant.mutate({ id: t.id, body: { status: "active" } })}
                  >
                    Activate
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    disabled={patchTenant.isPending || t.status === "suspended"}
                    onClick={() => patchTenant.mutate({ id: t.id, body: { status: "suspended" } })}
                  >
                    Suspend
                  </Button>
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => {
                      setInviteTenantId(t.id);
                      invite.reset();
                      resendInvite.reset();
                      setCreatedInvite(null);
                      setInviteOpen(true);
                    }}
                  >
                    Invite firm admin
                  </Button>
                  <Button
                    size="small"
                    variant="contained"
                    color="secondary"
                    disabled={
                      startingTenantPortal ||
                      (t.status !== "active" && t.status !== "trial")
                    }
                    onClick={() => void startTenantPortal(t.id)}
                  >
                    Open tenant portal
                  </Button>

                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    disabled={startingTenantPortal || deleteTenant.isPending}
                    onClick={() => {
                      setDeleteTenantId(t.id);
                      setDeleteTargetSlug(t.slug);
                      setDeleteConfirm("");
                      setDeleteOpen(true);
                    }}
                  >
                    Delete tenant
                  </Button>
                </Stack>
              </Box>
            ))}
          </Stack>
        </CardContent>
      </Card>

      <Dialog
        open={deleteOpen}
        onClose={() => {
          setDeleteOpen(false);
          setDeleteTenantId(null);
          setDeleteTargetSlug("");
          setDeleteConfirm("");
        }}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Delete tenant</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="error">
              This permanently deletes the tenant from the database and removes its uploaded files from storage.
            </Alert>
            <Typography variant="body2" color="text.secondary">
              To confirm, type <strong>{deleteTargetSlug}</strong> below.
            </Typography>
            <TextField
              label="Type tenant slug to confirm"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              fullWidth
              autoFocus
            />
            {deleteTenant.isError && (
              <Alert severity="error">
                {deleteTenant.error instanceof ApiError ? deleteTenant.error.message : "Delete failed"}
              </Alert>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setDeleteOpen(false);
              setDeleteTenantId(null);
              setDeleteTargetSlug("");
              setDeleteConfirm("");
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            disabled={deleteTenant.isPending || deleteTenantId == null || deleteConfirm.trim() !== deleteTargetSlug}
            onClick={() => deleteTenant.mutate()}
          >
            {deleteTenant.isPending ? "Deleting…" : "Delete permanently"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={inviteOpen}
        onClose={() => {
          setInviteOpen(false);
          setCreatedInvite(null);
        }}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Invite firm admin</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {!createdInvite && (
              <>
                <TextField label="Email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} fullWidth />
                <TextField label="Full name" value={inviteName} onChange={(e) => setInviteName(e.target.value)} fullWidth />
              </>
            )}
            {invite.isError && (
              <Alert severity="error">
                {invite.error instanceof ApiError ? invite.error.message : "Invite failed"}
              </Alert>
            )}
            {resendInvite.isError && (
              <Alert severity="error">
                {resendInvite.error instanceof ApiError ? resendInvite.error.message : "Resend failed"}
              </Alert>
            )}
            {createdInvite && (
              <>
                {createdInvite.email_sent ? (
                  <Alert severity="success">
                    {createdInvite.resent ? "Invitation email resent to" : "Invitation email sent to"}{" "}
                    {createdInvite.email}.
                  </Alert>
                ) : (
                  <Alert severity="warning">
                    Email was not sent
                    {createdInvite.email_error ? `: ${createdInvite.email_error}` : ""}. Share the link or token below.
                  </Alert>
                )}
                <Alert severity="info">
                  Invite link:{" "}
                  <Box component="pre" sx={{ whiteSpace: "pre-wrap", mt: 1, fontSize: 12 }}>
                    {createdInvite.invite_url}
                  </Box>
                  Token fallback:{" "}
                  <Box component="pre" sx={{ whiteSpace: "pre-wrap", mt: 1, fontSize: 12 }}>
                    {createdInvite.invite_token}
                  </Box>
                </Alert>
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setInviteOpen(false);
              setCreatedInvite(null);
            }}
          >
            Close
          </Button>
          {createdInvite ? (
            <Button
              variant="contained"
              disabled={inviteTenantId == null || resendInvite.isPending}
              onClick={() => resendInvite.mutate()}
            >
              {resendInvite.isPending ? "Sending…" : "Resend invitation"}
            </Button>
          ) : (
            <Button
              variant="contained"
              disabled={inviteTenantId == null || invite.isPending}
              onClick={() => invite.mutate()}
            >
              Create invite
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
