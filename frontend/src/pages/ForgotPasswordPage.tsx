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
import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { apiFetch, ApiError } from "../api/http";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setDone(null);
    setBusy(true);
    try {
      const res = await apiFetch<{ message: string }>("/auth/forgot-password", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      setDone(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box maxWidth={480} mx="auto" py={8} px={2}>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Forgot password
      </Typography>
      <Typography color="text.secondary" paragraph>
        Enter the email address on your firm account. We will send a link to choose a new password.
      </Typography>
      <Card variant="outlined">
        <CardContent>
          <form onSubmit={onSubmit}>
            <Stack spacing={2}>
              {error && <Alert severity="error">{error}</Alert>}
              {done && <Alert severity="success">{done}</Alert>}
              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                fullWidth
                autoComplete="email"
              />
              <Button type="submit" variant="contained" disabled={busy || !email.trim()} fullWidth>
                {busy ? "Sending…" : "Send reset link"}
              </Button>
              <Typography variant="body2" color="text.secondary" textAlign="center">
                <Link component={RouterLink} to="/login">
                  Back to sign in
                </Link>
              </Typography>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
