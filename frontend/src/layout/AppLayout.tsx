import {
  AppBar,
  Avatar,
  Box,
  Button,
  Collapse,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  BusinessOutlined,
  CompareArrowsOutlined,
  ExpandLess,
  ExpandMore,
  FolderOpenOutlined,
  GroupOutlined,
  KeyboardDoubleArrowLeft,
  KeyboardDoubleArrowRight,
  SettingsOutlined,
  TableChartOutlined,
} from "@mui/icons-material";
import { isPlatformTenantAccess, useAuth } from "../auth/AuthContext";
import { PlatformTenantAccessBanner } from "../components/PlatformTenantAccessBanner";
import { NAV_PERMISSIONS, hasPerm } from "../auth/permissions";
import { Link as RouterLink, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { BrandLogo } from "../components/BrandLogo";

const DRAWER_EXPANDED = 260;
const DRAWER_COLLAPSED = 72;

function roleLabel(role: string | null, platformTenantAccess: boolean) {
  if (platformTenantAccess) return "Platform Admin";
  if (role === "tenant_admin") return "Admin";
  if (role === "manager") return "Manager";
  if (role === "staff") return "Staff";
  return "Member";
}

type NavItem = { label: string; to: string; icon: React.ElementType; end?: boolean };

type NavChild = { label: string; to: string };

type NavGroup = {
  id: string;
  label: string;
  icon: React.ElementType;
  children: NavChild[];
};

const FIRM_NAV: NavItem[] = [
  { label: "Reconciliation", to: "/app/reconciliation", icon: CompareArrowsOutlined },
];

const navItemSx = {
  borderRadius: 1.5,
  mb: 0.25,
  "&.active": {
    bgcolor: "primary.main",
    color: "primary.contrastText",
    "& .MuiListItemIcon-root": { color: "inherit" },
  },
};

function NavLinkItem({
  item,
  collapsed,
}: {
  item: NavItem;
  collapsed: boolean;
}) {
  const Icon = item.icon;
  const btn = (
    <ListItemButton component={NavLink} to={item.to} end={item.end} sx={navItemSx}>
      <ListItemIcon sx={{ minWidth: collapsed ? 0 : 40, justifyContent: "center" }}>
        <Icon fontSize="small" />
      </ListItemIcon>
      {!collapsed && (
        <ListItemText primary={item.label} primaryTypographyProps={{ variant: "body2", fontWeight: 600 }} />
      )}
    </ListItemButton>
  );
  return collapsed ? (
    <Tooltip title={item.label} placement="right">
      {btn}
    </Tooltip>
  ) : (
    btn
  );
}

function NavGroupSection({
  group,
  collapsed,
  open,
  onToggle,
}: {
  group: NavGroup;
  collapsed: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  const location = useLocation();
  const childActive = group.children.some((c) => location.pathname.startsWith(c.to));
  const Icon = group.icon;

  if (collapsed) {
    const firstChild = group.children[0];
    return (
      <Tooltip title={`${group.label} · ${firstChild?.label ?? ""}`} placement="right">
        <ListItemButton
          component={NavLink}
          to={firstChild?.to ?? "#"}
          sx={{
            borderRadius: 1.5,
            mb: 0.25,
            "&.active": navItemSx["&.active"],
          }}
        >
          <ListItemIcon sx={{ minWidth: 0, justifyContent: "center" }}>
            <Icon fontSize="small" />
          </ListItemIcon>
        </ListItemButton>
      </Tooltip>
    );
  }

  return (
    <>
      <ListItemButton
        onClick={onToggle}
        sx={{
          borderRadius: 1.5,
          mb: 0.25,
          bgcolor: childActive && !open ? "action.selected" : undefined,
        }}
      >
        <ListItemIcon sx={{ minWidth: 40, justifyContent: "center" }}>
          <Icon fontSize="small" />
        </ListItemIcon>
        <ListItemText primary={group.label} primaryTypographyProps={{ variant: "body2", fontWeight: 600 }} />
        {open ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
      </ListItemButton>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          {group.children.map((child) => (
            <ListItemButton
              key={child.to}
              component={NavLink}
              to={child.to}
              sx={{
                ...navItemSx,
                pl: 4,
                py: 0.75,
              }}
            >
              <ListItemText
                primary={child.label}
                primaryTypographyProps={{ variant: "body2", fontWeight: 500, fontSize: "0.8125rem" }}
              />
            </ListItemButton>
          ))}
        </List>
      </Collapse>
    </>
  );
}

export function AppLayout() {
  const { me, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [userMenu, setUserMenu] = useState<null | HTMLElement>(null);
  const [dataMappingOpen, setDataMappingOpen] = useState(
    () => location.pathname.startsWith("/app/data-mapping")
  );
  const drawerW = collapsed ? DRAWER_COLLAPSED : DRAWER_EXPANDED;

  useEffect(() => {
    if (location.pathname.startsWith("/app/data-mapping")) {
      setDataMappingOpen(true);
    }
  }, [location.pathname]);

  const inTenantPortal = isPlatformTenantAccess(me);
  const isPlatform = Boolean(me?.is_platform_super_admin && !inTenantPortal);
  const isFirm = Boolean(me?.tenant_id != null && (!me.is_platform_super_admin || inTenantPortal));

  if (isPlatform) {
    return (
      <Box minHeight="100vh" bgcolor="background.default">
        <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
          <Toolbar sx={{ gap: 2 }}>
            <BrandLogo to="/" height={44} />
            <Box flex={1} />
            {me && (
              <Typography variant="body2" color="text.secondary">
                {me.full_name} · Platform
              </Typography>
            )}
            <Button component={RouterLink} to="/platform" color="inherit" size="small">
              Platform
            </Button>
            <Button size="small" variant="outlined" onClick={() => logout()}>
              Log out
            </Button>
          </Toolbar>
        </AppBar>
        <Box sx={{ maxWidth: 1200, mx: "auto", px: 3, py: 4 }}>
          <Outlet />
        </Box>
      </Box>
    );
  }

  if (!isFirm) {
    return (
      <Box minHeight="100vh" bgcolor="background.default">
        <Outlet />
      </Box>
    );
  }

  const perms = me?.permissions;
  const navItems: NavItem[] = [
    ...(hasPerm(perms, "cases.access")
      ? [{ label: "Cases", to: "/app/cases", icon: FolderOpenOutlined } satisfies NavItem]
      : []),
    ...FIRM_NAV.filter((item) => {
      const key = NAV_PERMISSIONS[item.to];
      if (!key) return true;
      return hasPerm(perms, key);
    }),
    ...(hasPerm(perms, "team.view")
      ? [{ label: "Team", to: "/app/team", icon: GroupOutlined } satisfies NavItem]
      : []),
    ...(hasPerm(perms, "settings.access")
      ? [{ label: "Settings", to: "/app/settings", icon: SettingsOutlined, end: false }]
      : []),
  ];

  const dataMappingGroup: NavGroup | null = hasPerm(perms, "data_mapping.access")
    ? {
        id: "data-mapping",
        label: "Data Mapping",
        icon: TableChartOutlined,
        children: [
          { label: "Master Fields", to: "/app/data-mapping/master-fields" },
          { label: "Purchase Register", to: "/app/data-mapping/purchase-register" },
          { label: "GSTR-2B", to: "/app/data-mapping/gstr-2b" },
        ],
      }
    : null;

  return (
    <Box minHeight="100vh" bgcolor="background.default" display="flex">
      <Drawer
        variant="permanent"
        sx={{
          width: drawerW,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: drawerW,
            boxSizing: "border-box",
            borderRight: 1,
            borderColor: "divider",
            bgcolor: "background.paper",
          },
        }}
      >
        <Box sx={{ px: collapsed ? 0.75 : 1, py: 1, minHeight: collapsed ? 56 : 64 }}>
          <BrandLogo to="/app" collapsed={collapsed} fill />
        </Box>
        <Divider />
        <List sx={{ px: 1, py: 1, flex: 1, overflow: "auto" }}>
          {navItems.slice(0, 1).map((item) => (
            <NavLinkItem key={item.to} item={item} collapsed={collapsed} />
          ))}
          {hasPerm(perms, "clients.access") && (
            <NavLinkItem
              item={{ label: "Client", to: "/app/clients", icon: BusinessOutlined }}
              collapsed={collapsed}
            />
          )}
          {dataMappingGroup && (
            <NavGroupSection
              group={dataMappingGroup}
              collapsed={collapsed}
              open={dataMappingOpen}
              onToggle={() => setDataMappingOpen((o) => !o)}
            />
          )}
          {navItems.slice(1).map((item) => (
            <NavLinkItem key={item.to} item={item} collapsed={collapsed} />
          ))}
        </List>
        <Divider />
        <Box sx={{ p: 1.5 }}>
          {!collapsed && (
            <Box sx={{ px: 1, py: 1, mb: 1 }}>
              <Typography variant="body2" fontWeight={700} noWrap>
                {me?.tenant_name ?? "Firm"}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {roleLabel(me?.role ?? null, Boolean(me?.platform_tenant_access))}
              </Typography>
            </Box>
          )}
          <Tooltip title={collapsed ? "Expand" : "Collapse"} placement="right">
            <IconButton
              size="small"
              onClick={() => setCollapsed((c) => !c)}
              sx={{ width: "100%", borderRadius: 1.5, color: "text.secondary" }}
            >
              {collapsed ? <KeyboardDoubleArrowRight fontSize="small" /> : <KeyboardDoubleArrowLeft fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>
      </Drawer>

      <Box component="div" flex={1} display="flex" flexDirection="column" minWidth={0}>
        {inTenantPortal && <PlatformTenantAccessBanner />}
        <AppBar
          position="sticky"
          color="inherit"
          elevation={0}
          sx={{ borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}
        >
          <Toolbar sx={{ gap: 2, minHeight: 64 }}>
            <Typography variant="h6" fontWeight={700} sx={{ flex: 1 }}>
              {me?.tenant_name ?? "Firm workspace"}
            </Typography>
            <Box
              onClick={(e) => setUserMenu(e.currentTarget)}
              sx={{ display: "flex", alignItems: "center", gap: 1, cursor: "pointer" }}
            >
              <Avatar sx={{ width: 32, height: 32, fontSize: "0.85rem", bgcolor: "primary.main" }}>
                {me?.full_name?.charAt(0)?.toUpperCase() ?? "?"}
              </Avatar>
              <Box sx={{ display: { xs: "none", sm: "block" } }}>
                <Typography variant="body2" fontWeight={600} lineHeight={1.2}>
                  {me?.full_name}
                </Typography>
                <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
                  {roleLabel(me?.role ?? null, inTenantPortal)}
                </Typography>
              </Box>
            </Box>
            <Menu anchorEl={userMenu} open={Boolean(userMenu)} onClose={() => setUserMenu(null)}>
              <MenuItem
                onClick={() => {
                  setUserMenu(null);
                  logout();
                }}
              >
                Log out
              </MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>
        <Box component="main" sx={{ flex: 1, overflow: "auto", p: { xs: 2, sm: 3 } }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
