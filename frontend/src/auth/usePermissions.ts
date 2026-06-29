import { useMemo } from "react";
import { useAuth } from "./AuthContext";
import { hasPerm } from "./permissions";

export function usePermissions() {
  const { me } = useAuth();
  const permissions = me?.permissions ?? null;

  return useMemo(
    () => ({
      permissions,
      can: (key: string) => hasPerm(permissions, key),
      role: me?.role ?? null,
    }),
    [permissions, me?.role]
  );
}
