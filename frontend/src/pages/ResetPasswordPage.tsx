import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Link,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const initialToken = useMemo(() => params.get("token") ?? "", [params]);
  const [token, setToken] = useState(initialToken);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setDone(null);
    setBusy(true);
    try {
      const res = await apiFetch<{ message: string }>("/auth/reset-password", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ token, password }),
      });
      setDone(res.message);
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reset password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box maxWidth={480} mx="auto" py={8} px={2}>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Choose a new password
      </Typography>
      <Typography color="text.secondary" paragraph>
        Use the link from your email, or paste the token below.
      </Typography>
      <Card variant="outlined">
        <CardContent>
          <form onSubmit={onSubmit}>
            <Stack spacing={2}>
              {error && <Alert severity="error">{error}</Alert>}
              {done && <Alert severity="success">{done}</Alert>}
              <TextField
                label="Reset token"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
                fullWidth
                multiline
                minRows={2}
              />
              <TextField
                label="New password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                fullWidth
                inputProps={{ minLength: 8 }}
                helperText="At least 8 characters"
              />
              <Button type="submit" variant="contained" disabled={busy || password.length < 8} fullWidth>
                {busy ? "Saving…" : "Update password"}
              </Button>
              <Typography variant="body2" color="text.secondary" textAlign="center">
                <Link component={RouterLink} to="/forgot-password">
                  Request a new link
                </Link>
                {" · "}
                <Link component={RouterLink} to="/login">
                  Sign in
                </Link>
              </Typography>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
