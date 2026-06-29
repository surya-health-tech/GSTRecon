import { Alert, Box, CircularProgress } from "@mui/material";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { defaultFirmHomePath, hasPerm } from "./permissions";

export function RequirePermission({
  permission,
  children,
  redirectTo,
}: {
  permission: string;
  children: React.ReactNode;
  /** When set, missing permission redirects instead of showing a warning. */
  redirectTo?: string;
}) {
  const { me, loading } = useAuth();
  const fallback = redirectTo ?? defaultFirmHomePath(me?.permissions);
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress size={28} />
      </Box>
    );
  }
  if (!me?.permissions) return <Navigate to={fallback} replace />;
  if (!hasPerm(me.permissions, permission)) {
    if (redirectTo !== undefined) {
      return <Navigate to={fallback} replace />;
    }
    return (
      <Box p={3}>
        <Alert severity="warning">You do not have permission to view this page.</Alert>
      </Box>
    );
  }
  return <>{children}</>;
}
