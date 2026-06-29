import { Box, List, ListItemButton, ListItemText, Stack, Typography } from "@mui/material";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const SETTINGS_LINKS = [
  { label: "Firm Profile", to: "/app/settings", end: true },
  { label: "Role Permissions", to: "/app/settings/role-permissions", adminOnly: true },
];

export function SettingsLayout() {
  const { me } = useAuth();
  const isAdmin = me?.role === "tenant_admin";

  const links = SETTINGS_LINKS.filter((l) => !l.adminOnly || isAdmin);

  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={3} alignItems="flex-start">
      <Box
        sx={{
          width: { xs: "100%", md: 220 },
          flexShrink: 0,
          border: 1,
          borderColor: "divider",
          borderRadius: 2,
          bgcolor: "background.paper",
          overflow: "hidden",
        }}
      >
        <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: "divider" }}>
          <Typography variant="overline" color="text.secondary" fontWeight={700}>
            Settings
          </Typography>
        </Box>
        <List dense disablePadding>
          {links.map((l) => (
            <ListItemButton
              key={l.to}
              component={NavLink}
              to={l.to}
              end={"end" in l ? l.end : false}
              sx={{
                "&.active": { bgcolor: "action.selected", borderLeft: 3, borderColor: "primary.main" },
              }}
            >
              <ListItemText primary={l.label} primaryTypographyProps={{ variant: "body2", fontWeight: 600 }} />
            </ListItemButton>
          ))}
        </List>
      </Box>
      <Box flex={1} minWidth={0} width="100%">
        <Outlet />
      </Box>
    </Stack>
  );
}
