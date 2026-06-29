import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";

export function AcceptInvitePage() {
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
      const res = await apiFetch<{ message: string; email: string }>("/auth/accept-invitation", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ token, password }),
      });
      setDone(res.message ? `${res.message} (${res.email})` : `Account ready for ${res.email}. You can sign in now.`);
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept invitation");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box maxWidth={480} mx="auto" py={8} px={2}>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Accept invitation
      </Typography>
      <Typography color="text.secondary" paragraph>
        Paste the token shown in the platform console after inviting a firm admin, then choose a password.
      </Typography>
      <Card variant="outlined">
        <CardContent>
          <form onSubmit={onSubmit}>
            <Stack spacing={2}>
              {error && <Alert severity="error">{error}</Alert>}
              {done && <Alert severity="success">{done}</Alert>}
              <TextField
                label="Invite token"
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
              <Button type="submit" variant="contained" disabled={busy} fullWidth>
                {busy ? "Saving…" : "Activate account"}
              </Button>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
