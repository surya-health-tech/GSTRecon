import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { defaultFirmHomePath, hasPerm } from "./permissions";

export function RequireAnyPermission({
  permissions,
  children,
}: {
  permissions: string[];
  children: React.ReactNode;
}) {
  const { me, loading } = useAuth();
  const fallback = defaultFirmHomePath(me?.permissions);
  if (loading) return null;
  if (!me?.permissions) return <Navigate to={fallback} replace />;
  const allowed = permissions.some((p) => hasPerm(me.permissions, p));
  if (!allowed) {
    return <Navigate to={fallback} replace />;
  }
  return <>{children}</>;
}
