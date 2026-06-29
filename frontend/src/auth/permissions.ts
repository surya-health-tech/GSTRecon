/** Permission keys returned by GET /auth/me (permissions map). */

export type PermissionKey = string;

export function hasPerm(permissions: Record<string, boolean> | null | undefined, key: string): boolean {
  return Boolean(permissions?.[key]);
}

export function hasAnyPerm(
  permissions: Record<string, boolean> | null | undefined,
  keys: string[]
): boolean {
  return keys.some((k) => hasPerm(permissions, k));
}

export const FIRM_HOME_CANDIDATES: { path: string; permission?: string }[] = [
  { path: "/app/cases", permission: "cases.access" },
  { path: "/app/reconciliation", permission: "reconciliation.access" },
  { path: "/app/clients", permission: "clients.access" },
  { path: "/app/data-mapping/master-fields", permission: "data_mapping.access" },
  { path: "/app/team", permission: "team.view" },
  { path: "/app/settings", permission: "settings.access" },
];

export function defaultFirmHomePath(permissions: Record<string, boolean> | null | undefined): string {
  for (const { path, permission } of FIRM_HOME_CANDIDATES) {
    if (!permission || hasPerm(permissions, permission)) return path;
  }
  return "/app/reconciliation";
}

export const NAV_PERMISSIONS: Record<string, string | undefined> = {
  "/app/cases": "cases.access",
  "/app/reconciliation": "reconciliation.access",
  "/app/clients": "clients.access",
  "/app/data-mapping": "data_mapping.access",
  "/app/team": "team.view",
  "/app/settings": "settings.access",
};
