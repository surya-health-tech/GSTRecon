import { Alert, Box, Button, Stack, Typography } from "@mui/material";
import { useAuth } from "../auth/AuthContext";

export function PlatformTenantAccessBanner() {
  const { me, endTenantPortal, endingTenantPortal } = useAuth();
  const access = me?.platform_tenant_access;
  if (!access) return null;

  const adminLabel = access.platform_admin_email
    ? `${access.platform_admin_name} (${access.platform_admin_email})`
    : access.platform_admin_name;

  return (
    <Alert
      severity="info"
      icon={false}
      sx={{
        borderRadius: 0,
        borderBottom: 1,
        borderColor: "divider",
        "& .MuiAlert-message": { width: "100%" },
      }}
    >
      <Stack
        direction={{ xs: "column", sm: "row" }}
        alignItems={{ xs: "flex-start", sm: "center" }}
        justifyContent="space-between"
        gap={1.5}
        width="100%"
      >
        <Box>
          <Typography variant="subtitle2" fontWeight={700}>
            You are viewing this tenant as Platform Admin: {access.tenant_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Signed in as {adminLabel} · Tenant Admin privileges · This is a platform access session, not the
            firm&apos;s tenant admin account.
          </Typography>
        </Box>
        <Button
          variant="outlined"
          color="inherit"
          size="small"
          onClick={() => void endTenantPortal()}
          disabled={endingTenantPortal}
          sx={{ flexShrink: 0, bgcolor: "background.paper" }}
        >
          Exit Tenant Portal
        </Button>
      </Stack>
    </Alert>
  );
}
