import {
  Box,
  Button,
  Container,
  Grid,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import CompareArrowsOutlinedIcon from "@mui/icons-material/CompareArrowsOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import { Link as RouterLink } from "react-router-dom";
import { isPlatformTenantAccess, useAuth } from "../auth/AuthContext";
import { defaultFirmHomePath } from "../auth/permissions";
import { BrandLogo } from "../components/BrandLogo";
import { FirmSignInCard } from "../components/FirmSignInCard";
import { BRAND_NAME } from "../brand";

const FEATURES = [
  {
    icon: <CompareArrowsOutlinedIcon color="primary" />,
    title: "GSTR-2B reconciliation",
    description: "Match portal GSTR-2B data against purchase books with automated categorization.",
  },
  {
    icon: <UploadFileOutlinedIcon color="primary" />,
    title: "Excel uploads",
    description: "Import portal and book data from Excel exports with field mapping support.",
  },
  {
    icon: <GroupsOutlinedIcon color="primary" />,
    title: "Team & roles",
    description: "Invite firm staff, assign admin/manager/staff roles, and control permissions.",
  },
  {
    icon: <LockOutlinedIcon color="primary" />,
    title: "Multi-tenant security",
    description: "Each firm works in an isolated workspace provisioned by the platform administrator.",
  },
];

export function HomePage() {
  const { me, loading } = useAuth();

  return (
    <Box minHeight="100vh" display="flex" flexDirection="column" bgcolor="background.default">
      <Box component="header" borderBottom={1} borderColor="divider" bgcolor="background.paper">
        <Container maxWidth="lg">
          <Stack
            direction={{ xs: "column", sm: "row" }}
            alignItems={{ xs: "flex-start", sm: "center" }}
            justifyContent="space-between"
            py={2}
            spacing={2}
          >
            <BrandLogo to="/" height={40} />
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Button component="a" href="#firm-sign-in" size="small">
                Firm sign in
              </Button>
              {!loading && isPlatformTenantAccess(me) && (
                <Button component={RouterLink} to="/app" variant="contained" size="small">
                  Tenant portal
                </Button>
              )}
              {!loading && me?.is_platform_super_admin && !isPlatformTenantAccess(me) && (
                <Button component={RouterLink} to="/platform" variant="contained" size="small">
                  Platform console
                </Button>
              )}
              {!loading && me && !me.is_platform_super_admin && me.tenant_id && (
                <Button
                  component={RouterLink}
                  to={defaultFirmHomePath(me.permissions)}
                  variant="contained"
                  size="small"
                >
                  Open firm app
                </Button>
              )}
            </Stack>
          </Stack>
        </Container>
      </Box>

      <Box component="main" flex={1}>
        <Container maxWidth="lg" sx={{ py: { xs: 5, md: 8 } }}>
          <Box mb={6}>
            <Typography variant="overline" color="text.secondary" fontWeight={700}>
              {BRAND_NAME}
            </Typography>
            <Typography variant="h4" fontWeight={700} gutterBottom sx={{ mt: 0.5 }}>
              Automate GSTR-2B vs purchase book reconciliation
            </Typography>
            <Typography color="text.secondary" paragraph sx={{ mb: 0, maxWidth: 720 }}>
              Upload GSTR-2B portal data and purchase register exports, reconcile ITC automatically,
              and export matched, mismatch, and open-item reports for your clients.
            </Typography>
          </Box>

          <Grid container spacing={3} mb={8}>
            {FEATURES.map((feature) => (
              <Grid key={feature.title} item xs={12} sm={6}>
                <Stack direction="row" spacing={2} alignItems="flex-start">
                  <Box pt={0.25}>{feature.icon}</Box>
                  <Box>
                    <Typography fontWeight={600} gutterBottom>
                      {feature.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {feature.description}
                    </Typography>
                  </Box>
                </Stack>
              </Grid>
            ))}
          </Grid>

          <Box id="firm-sign-in" sx={{ scrollMarginTop: 88 }}>
            <Typography variant="h5" fontWeight={700} gutterBottom textAlign="center">
              Firm sign in
            </Typography>
            <Typography color="text.secondary" textAlign="center" mb={4} maxWidth={560} mx="auto">
              New firm users accept an invitation from their administrator. Platform staff use the
              platform console after signing in.
            </Typography>
            <Box maxWidth={480} mx="auto">
              <FirmSignInCard />
            </Box>
          </Box>
        </Container>
      </Box>

      <Box component="footer" borderTop={1} borderColor="divider" bgcolor="background.paper" py={3} mt="auto">
        <Container maxWidth="lg">
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
            <Typography variant="body2" color="text.secondary">
              © 2026 Accsys Consulting. All rights reserved.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <Link component={RouterLink} to="/accept-invite" underline="hover">
                Accept invitation
              </Link>
            </Typography>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
}
