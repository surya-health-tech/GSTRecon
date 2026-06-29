import {
  Alert,
  Button,
  Card,
  CardContent,
  Link,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { isPlatformTenantAccess, useAuth } from "../auth/AuthContext";
import { defaultFirmHomePath } from "../auth/permissions";
import { ApiError } from "../api/http";

type FirmSignInCardProps = {
  title?: string;
  showInviteLink?: boolean;
  compact?: boolean;
};

export function FirmSignInCard({
  title = "Firm sign in",
  showInviteLink = true,
  compact = false,
}: FirmSignInCardProps) {
  const { login, me, loading } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get("reason") === "expired";
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!me) return;
    if (me.is_platform_super_admin && isPlatformTenantAccess(me)) {
      navigate("/app", { replace: true });
    } else if (me.is_platform_super_admin) {
      navigate("/platform", { replace: true });
    } else if (me.tenant_id) {
      navigate(defaultFirmHomePath(me.permissions), { replace: true });
    }
  }, [me, loading, navigate]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(loginId, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return null;
  }

  if (me) {
    return null;
  }

  return (
    <Card variant="outlined" id="firm-sign-in">
      <CardContent>
        <Typography variant={compact ? "h6" : "h5"} fontWeight={700} gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          For firm staff and platform administrators.
        </Typography>
        <form onSubmit={onSubmit}>
          <Stack spacing={2}>
            {sessionExpired && (
              <Alert severity="info">
                Your session ended. Sign in again to pick up where you left off.
              </Alert>
            )}
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="Email or phone number"
              type="text"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              required
              fullWidth
              autoComplete="username"
              helperText="Use your email or local phone number (no country code) based on how your account was created."
              inputProps={{ "data-testid": "login-email" }}
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
              autoComplete="current-password"
              inputProps={{ "data-testid": "login-password" }}
            />
            <Typography variant="body2" textAlign="right">
              <Link component={RouterLink} to="/forgot-password">
                Forgot password?
              </Link>
            </Typography>
            <Button
              type="submit"
              variant="contained"
              disabled={busy}
              fullWidth
              data-testid="login-submit"
            >
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </Stack>
        </form>
        {showInviteLink && (
          <Typography variant="body2" color="text.secondary" mt={2}>
            Have an invite token?{" "}
            <Link component={RouterLink} to="/accept-invite">
              Accept invitation
            </Link>
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
