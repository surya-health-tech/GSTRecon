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
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import EditOutlined from "@mui/icons-material/EditOutlined";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiFetch, ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { usePermissions } from "../auth/usePermissions";
import { DEFAULT_PHONE_COUNTRY_CODE, formatPhoneDisplay, PhoneField } from "../components/PhoneField";

type FirmUser = {
  user_id: number;
  email: string | null;
  full_name: string;
  role: string;
  membership_active: boolean;
  login_method: string;
  phone: string | null;
  phone_country_code: string | null;
  location_id: number | null;
  location_name: string | null;
  location_status: string | null;
};

type TeamMember = {
  kind: "member" | "invitation";
  status: "active" | "inactive" | "invited" | "expired";
  full_name: string;
  email: string | null;
  role: string;
  user_id: number | null;
  invitation_id: number | null;
  membership_active: boolean | null;
  login_method: string | null;
  phone: string | null;
  phone_country_code: string | null;
  invitation_expires_at: string | null;
  location_id: number | null;
  location_name: string | null;
  location_status: string | null;
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

type CreateMemberResult = {
  mode: "invitation" | "user";
  invitation: InviteResult | null;
  user: FirmUser | null;
  phone_account_email_sent: boolean | null;
  phone_account_email_error: string | null;
};

const ROLE_LABELS: Record<string, string> = {
  staff: "Staff",
  manager: "Manager",
  tenant_admin: "Firm admin",
};

const LOGIN_METHOD_LABELS: Record<string, string> = {
  email: "Email",
  phone_password: "Phone Number",
  phone_otp: "Phone OTP",
};

const STATUS_LABELS: Record<TeamMember["status"], string> = {
  active: "Active",
  inactive: "Inactive",
  invited: "Invitation sent",
  expired: "Invitation expired",
};

function statusChipColor(
  status: TeamMember["status"]
): "default" | "success" | "warning" | "error" {
  if (status === "active") return "success";
  if (status === "invited") return "warning";
  if (status === "expired") return "error";
  return "default";
}

function teamRowKey(row: TeamMember) {
  return row.kind === "member" ? `member-${row.user_id}` : `invitation-${row.invitation_id}`;
}

function emailDisplay(email: string | null | undefined) {
  const e = (email ?? "").trim();
  return e || "Not provided";
}

export function TeamPage() {
  const qc = useQueryClient();
  const { me } = useAuth();
  const { can, role: myRole } = usePermissions();
  const isFirmAdmin = myRole === "tenant_admin";
  const canAssignRoles = isFirmAdmin || can("team.assign_roles");
  const canRemove = isFirmAdmin || can("team.remove");
  const canEdit = isFirmAdmin || can("team.edit");
  const isManager = myRole === "manager";

  const usersQ = useQuery({
    queryKey: ["firm-users"],
    queryFn: () => apiFetch<TeamMember[]>("/app/users"),
  });

  const toggle = useMutation({
    mutationFn: ({ userId, active }: { userId: number; active: boolean }) =>
      apiFetch<FirmUser>(`/app/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ membership_active: active }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["firm-users"] }),
  });

  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      apiFetch<FirmUser>(`/app/users/${userId}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["firm-users"] }),
  });

  const removeUser = useMutation({
    mutationFn: (userId: number) => apiFetch<void>(`/app/users/${userId}`, { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["firm-users"] }),
  });

  const [addOpen, setAddOpen] = useState(false);
  const [addName, setAddName] = useState("");
  const [addLoginMethod, setAddLoginMethod] = useState<"email" | "phone_password">("email");
  const [addEmail, setAddEmail] = useState("");
  const [addPhone, setAddPhone] = useState("");
  const [addPhoneCc, setAddPhoneCc] = useState(DEFAULT_PHONE_COUNTRY_CODE);
  const [addRole, setAddRole] = useState("staff");
  const [createResult, setCreateResult] = useState<CreateMemberResult | null>(null);

  const [editUser, setEditUser] = useState<FirmUser | null>(null);
  const [editName, setEditName] = useState("");
  const [editLoginMethod, setEditLoginMethod] = useState<"email" | "phone_password">("email");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editPhoneCc, setEditPhoneCc] = useState(DEFAULT_PHONE_COUNTRY_CODE);
  const [editRole, setEditRole] = useState("staff");

  const [roleChangeConfirm, setRoleChangeConfirm] = useState<{
    userId: number;
    fullName: string;
    fromRole: string;
    toRole: string;
  } | null>(null);

  const resetAddForm = () => {
    setAddName("");
    setAddLoginMethod("email");
    setAddEmail("");
    setAddPhone("");
    setAddPhoneCc(DEFAULT_PHONE_COUNTRY_CODE);
    setAddRole("staff");
    setCreateResult(null);
  };

  const openAddDialog = () => {
    resetAddForm();
    createMember.reset();
    setAddOpen(true);
  };

  const closeAddDialog = () => {
    setAddOpen(false);
    resetAddForm();
    createMember.reset();
  };

  const openEdit = (u: TeamMember) => {
    if (u.kind !== "member" || u.user_id == null) return;
    setEditUser({
      user_id: u.user_id,
      full_name: u.full_name,
      email: u.email,
      role: u.role,
      membership_active: u.membership_active ?? true,
      login_method: u.login_method ?? "email",
      phone: u.phone,
      phone_country_code: u.phone_country_code,
      location_id: null,
      location_name: null,
      location_status: null,
    });
    setEditName(u.full_name);
    setEditLoginMethod(u.login_method === "phone_password" ? "phone_password" : "email");
    setEditEmail(u.email ?? "");
    setEditPhone(u.phone ?? "");
    setEditPhoneCc(u.phone_country_code ?? DEFAULT_PHONE_COUNTRY_CODE);
    setEditRole(u.role);
    updateMember.reset();
  };

  const createMember = useMutation({
    mutationFn: () =>
      apiFetch<CreateMemberResult>("/app/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: addName.trim(),
          role: addRole,
          login_method: addLoginMethod,
          email: addEmail.trim() || null,
          phone: addPhone.trim() || null,
          phone_country_code: addPhone.trim() ? addPhoneCc : null,
        }),
      }),
    onSuccess: (data) => {
      setCreateResult(data);
      void qc.invalidateQueries({ queryKey: ["firm-users"] });
    },
  });

  const updateMember = useMutation({
    mutationFn: () => {
      if (!editUser) throw new Error("No user");
      return apiFetch<FirmUser>(`/app/users/${editUser.user_id}/profile`, {
        method: "PATCH",
        body: JSON.stringify({
          full_name: editName.trim(),
          role: editRole,
          login_method: editLoginMethod,
          email: editEmail.trim() || null,
          phone: editPhone.trim() || null,
          phone_country_code: editPhone.trim() ? editPhoneCc : null,
        }),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["firm-users"] });
      setEditUser(null);
    },
  });

  const resendInvite = useMutation({
    mutationFn: (invitationId: number) =>
      apiFetch<InviteResult>(`/app/invitations/${invitationId}/resend`, { method: "POST" }),
    onSuccess: (data) => {
      setCreateResult((prev) =>
        prev?.mode === "invitation" ? { ...prev, invitation: data } : prev
      );
      void qc.invalidateQueries({ queryKey: ["firm-users"] });
    },
  });

  const addValid = useMemo(() => {
    if (!addName.trim()) return false;
    if (addLoginMethod === "email") return Boolean(addEmail.trim());
    return Boolean(addPhone.trim());
  }, [addName, addLoginMethod, addEmail, addPhone]);

  const editValid = useMemo(() => {
    if (!editName.trim()) return false;
    if (editLoginMethod === "email") return Boolean(editEmail.trim());
    return Boolean(editPhone.trim());
  }, [editName, editLoginMethod, editEmail, editPhone]);

  return (
    <Stack spacing={3}>
      <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
        <Typography variant="h4" fontWeight={700}>
          Team
        </Typography>
        {can("team.add") && (
          <Button variant="contained" onClick={openAddDialog}>
            Add team member
          </Button>
        )}
      </Box>
      <Typography color="text.secondary">
        Email users receive an invitation link. Phone users are created with a temporary password emailed to firm
        administrators only. SMS OTP login will be added later.
      </Typography>

      <Card variant="outlined">
        <CardContent>
          {usersQ.isLoading && <Typography>Loading…</Typography>}
          {usersQ.isError && (
            <Alert severity="error">
              {usersQ.error instanceof ApiError ? usersQ.error.message : "Failed to load team"}
            </Alert>
          )}
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Phone</TableCell>
                <TableCell>Login method</TableCell>
                <TableCell>Role</TableCell>
                <TableCell align="right">Active</TableCell>
                {(canEdit || can("team.add")) && <TableCell align="right">Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {(usersQ.data ?? []).map((u) => {
                const isMember = u.kind === "member" && u.user_id != null;
                const isSelf = isMember && u.user_id === me?.id;
                const loginMethod = u.login_method ?? "email";
                return (
                  <TableRow key={teamRowKey(u)}>
                    <TableCell>{u.full_name}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={STATUS_LABELS[u.status]}
                        color={statusChipColor(u.status)}
                        variant="outlined"
                        sx={{ fontWeight: 600 }}
                      />
                    </TableCell>
                    <TableCell>{emailDisplay(u.email)}</TableCell>
                    <TableCell>
                      {u.phone ? formatPhoneDisplay(u.phone_country_code, u.phone) : "—"}
                    </TableCell>
                    <TableCell>
                      {u.kind === "invitation"
                        ? "Email"
                        : LOGIN_METHOD_LABELS[loginMethod] ?? loginMethod}
                    </TableCell>
                    <TableCell>
                      {isMember && canAssignRoles && !isSelf ? (
                        <TextField
                          select
                          size="small"
                          SelectProps={{ native: true }}
                          value={u.role}
                          disabled={changeRole.isPending}
                          onChange={(e) => {
                            const nextRole = e.target.value;
                            if (nextRole === u.role) return;
                            setRoleChangeConfirm({
                              userId: u.user_id!,
                              fullName: u.full_name,
                              fromRole: u.role,
                              toRole: nextRole,
                            });
                          }}
                        >
                          <option value="staff">Staff</option>
                          <option value="manager">Manager</option>
                          <option value="tenant_admin">Firm admin</option>
                        </TextField>
                      ) : (
                        ROLE_LABELS[u.role] ?? u.role
                      )}
                    </TableCell>
                    <TableCell align="right">
                      {isMember ? (
                        <Switch
                          checked={Boolean(u.membership_active)}
                          disabled={toggle.isPending || isSelf}
                          onChange={(_, checked) => toggle.mutate({ userId: u.user_id!, active: checked })}
                        />
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          —
                        </Typography>
                      )}
                    </TableCell>
                    {(canEdit || can("team.add")) && (
                      <TableCell align="right">
                        {isMember && canEdit && (
                          <IconButton size="small" aria-label="Edit user" onClick={() => openEdit(u)}>
                            <EditOutlined fontSize="small" />
                          </IconButton>
                        )}
                        {u.kind === "invitation" && u.invitation_id != null && can("team.add") && (
                          <Button
                            size="small"
                            variant="outlined"
                            sx={{ textTransform: "none", ml: isMember && canEdit ? 0.5 : 0 }}
                            disabled={resendInvite.isPending}
                            onClick={() => resendInvite.mutate(u.invitation_id!)}
                          >
                            Resend invite
                          </Button>
                        )}
                        {isMember && canRemove && !isSelf && (
                          <IconButton
                            size="small"
                            color="error"
                            aria-label="Remove user"
                            disabled={removeUser.isPending}
                            onClick={() => {
                              if (
                                window.confirm(
                                  `Remove ${u.full_name} from this firm? This cannot be undone if they have no linked activity.`
                                )
                              ) {
                                removeUser.mutate(u.user_id!);
                              }
                            }}
                          >
                            <DeleteOutline fontSize="small" />
                          </IconButton>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={addOpen} onClose={closeAddDialog} fullWidth maxWidth="sm">
        <DialogTitle>Add team member</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {!createResult && (
              <>
                <TextField
                  label="Full name"
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  fullWidth
                  required
                />
                <TextField
                  label="Login method"
                  select
                  SelectProps={{ native: true }}
                  value={addLoginMethod}
                  onChange={(e) => setAddLoginMethod(e.target.value as "email" | "phone_password")}
                  fullWidth
                  required
                >
                  <option value="email">Email</option>
                  <option value="phone_password">Phone Number</option>
                </TextField>
                <TextField
                  label="Email"
                  value={addEmail}
                  onChange={(e) => setAddEmail(e.target.value)}
                  fullWidth
                  required={addLoginMethod === "email"}
                  helperText={
                    addLoginMethod === "phone_password"
                      ? "Optional for phone users (notifications / recovery)."
                      : "Required for email login."
                  }
                />
                {(addLoginMethod === "phone_password" || addPhone.trim()) && (
                  <PhoneField
                    countryCode={addPhoneCc}
                    phone={addPhone}
                    onCountryCodeChange={setAddPhoneCc}
                    onPhoneChange={setAddPhone}
                    required={addLoginMethod === "phone_password"}
                    defaultCountryCode={DEFAULT_PHONE_COUNTRY_CODE}
                  />
                )}
                <TextField
                  label="Role"
                  select
                  SelectProps={{ native: true }}
                  value={addRole}
                  onChange={(e) => setAddRole(e.target.value)}
                  fullWidth
                >
                  <option value="staff">Staff</option>
                  {!isManager && <option value="manager">Manager</option>}
                  {!isManager && <option value="tenant_admin">Firm admin</option>}
                </TextField>
              </>
            )}
            {createMember.isError && (
              <Alert severity="error">
                {createMember.error instanceof ApiError ? createMember.error.message : "Could not add member"}
              </Alert>
            )}
            {createResult?.mode === "user" && (
              <Alert severity="success">
                Phone-login user <strong>{createResult.user?.full_name}</strong> was created. A temporary password was
                emailed to firm administrator(s) only.
                {createResult.phone_account_email_sent === false && (
                  <>
                    {" "}
                    Admin email could not be sent
                    {createResult.phone_account_email_error
                      ? `: ${createResult.phone_account_email_error}`
                      : "."}
                  </>
                )}
              </Alert>
            )}
            {createResult?.mode === "invitation" && createResult.invitation && (
              <>
                {createResult.invitation.email_sent ? (
                  <Alert severity="success">
                    Invitation email sent to {createResult.invitation.email}.
                  </Alert>
                ) : (
                  <Alert severity="warning">
                    Email was not sent
                    {createResult.invitation.email_error
                      ? `: ${createResult.invitation.email_error}`
                      : ""}
                    . Share the link below.
                  </Alert>
                )}
                <Alert severity="info">
                  Invite link:{" "}
                  <Box component="pre" sx={{ whiteSpace: "pre-wrap", mt: 1, fontSize: 12 }}>
                    {createResult.invitation.invite_url}
                  </Box>
                </Alert>
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeAddDialog}>Close</Button>
          {createResult?.mode === "invitation" && createResult.invitation ? (
            <Button
              variant="contained"
              disabled={resendInvite.isPending}
              onClick={() => resendInvite.mutate(createResult.invitation!.invitation_id)}
            >
              Resend invitation
            </Button>
          ) : !createResult ? (
            <Button variant="contained" disabled={createMember.isPending || !addValid} onClick={() => createMember.mutate()}>
              {createMember.isPending ? "Saving…" : "Add member"}
            </Button>
          ) : null}
        </DialogActions>
      </Dialog>

      <Dialog open={editUser != null} onClose={() => setEditUser(null)} fullWidth maxWidth="sm">
        <DialogTitle>Edit team member</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Full name" value={editName} onChange={(e) => setEditName(e.target.value)} fullWidth />
            <TextField
              label="Login method"
              select
              SelectProps={{ native: true }}
              value={editLoginMethod}
              onChange={(e) => setEditLoginMethod(e.target.value as "email" | "phone_password")}
              fullWidth
            >
              <option value="email">Email</option>
              <option value="phone_password">Phone Number</option>
            </TextField>
            <TextField
              label="Email"
              value={editEmail}
              onChange={(e) => setEditEmail(e.target.value)}
              fullWidth
              required={editLoginMethod === "email"}
              helperText={editLoginMethod === "phone_password" ? "Optional" : "Required"}
            />
            <PhoneField
              countryCode={editPhoneCc}
              phone={editPhone}
              onCountryCodeChange={setEditPhoneCc}
              onPhoneChange={setEditPhone}
              required={editLoginMethod === "phone_password"}
              defaultCountryCode={DEFAULT_PHONE_COUNTRY_CODE}
            />
            {canAssignRoles && editUser?.user_id !== me?.id && (
              <TextField
                label="Role"
                select
                SelectProps={{ native: true }}
                value={editRole}
                onChange={(e) => setEditRole(e.target.value)}
                fullWidth
              >
                <option value="staff">Staff</option>
                {!isManager && <option value="manager">Manager</option>}
                {!isManager && <option value="tenant_admin">Firm admin</option>}
              </TextField>
            )}
            {updateMember.isError && (
              <Alert severity="error">
                {updateMember.error instanceof ApiError ? updateMember.error.message : "Update failed"}
              </Alert>
            )}
            {editLoginMethod === "phone_password" && editUser?.login_method === "email" && (
              <Alert severity="info">
                Switching to phone login will generate a new temporary password and email it to firm administrators.
              </Alert>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditUser(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={updateMember.isPending || !editValid}
            onClick={() => updateMember.mutate()}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={roleChangeConfirm != null} onClose={() => setRoleChangeConfirm(null)} fullWidth maxWidth="xs">
        <DialogTitle>Change role?</DialogTitle>
        <DialogContent>
          {roleChangeConfirm && (
            <Typography>
              Change <strong>{roleChangeConfirm.fullName}</strong> from{" "}
              <strong>{ROLE_LABELS[roleChangeConfirm.fromRole] ?? roleChangeConfirm.fromRole}</strong> to{" "}
              <strong>{ROLE_LABELS[roleChangeConfirm.toRole] ?? roleChangeConfirm.toRole}</strong>?
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRoleChangeConfirm(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={changeRole.isPending || roleChangeConfirm == null}
            onClick={() => {
              if (!roleChangeConfirm) return;
              changeRole.mutate(
                { userId: roleChangeConfirm.userId, role: roleChangeConfirm.toRole },
                { onSettled: () => setRoleChangeConfirm(null) }
              );
            }}
          >
            Change role
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
