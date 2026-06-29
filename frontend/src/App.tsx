import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layout/AppLayout";
import { AcceptInvitePage } from "./pages/AcceptInvitePage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { FirmSettingsPage } from "./pages/FirmSettingsPage";
import { RolePermissionsPage } from "./pages/RolePermissionsPage";
import { SettingsLayout } from "./layout/SettingsLayout";
import { FirmAppHome } from "./auth/FirmAppHome";
import { RequirePermission } from "./auth/RequirePermission";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { PlatformPage } from "./pages/PlatformPage";
import { TeamPage } from "./pages/TeamPage";
import { ClientsPage } from "./pages/ClientsPage";
import { Gstr2bMappingFormPage } from "./pages/Gstr2bMappingFormPage";
import { Gstr2bMappingsPage } from "./pages/Gstr2bMappingsPage";
import { MasterFieldsPage } from "./pages/MasterFieldsPage";
import { ReconciliationCaseDetailPage } from "./pages/ReconciliationCaseDetailPage";
import { ReconciliationCaseFormPage } from "./pages/ReconciliationCaseFormPage";
import { ReconciliationCasesPage } from "./pages/ReconciliationCasesPage";
import { PurchaseRegisterMappingFormPage } from "./pages/PurchaseRegisterMappingFormPage";
import { PurchaseRegisterMappingsPage } from "./pages/PurchaseRegisterMappingsPage";
import { isPlatformTenantAccess, useAuth } from "./auth/AuthContext";
import { Box, CircularProgress } from "@mui/material";

function Loading() {
  return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
      <CircularProgress />
    </Box>
  );
}

function RequirePlatform({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  if (!me) return <Navigate to="/" replace />;
  if (!me.is_platform_super_admin) return <Navigate to="/app" replace />;
  if (isPlatformTenantAccess(me)) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

function RequireFirm({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  if (!me) return <Navigate to="/" replace />;
  if (me.is_platform_super_admin && !isPlatformTenantAccess(me)) {
    return <Navigate to="/platform" replace />;
  }
  if (!me.tenant_id) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireTenantAdmin({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  const ok = me && (me.role === "tenant_admin" || isPlatformTenantAccess(me));
  if (!ok) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />
      <Route path="/" element={<HomePage />} />
      <Route
        path="/platform"
        element={
          <RequirePlatform>
            <AppLayout />
          </RequirePlatform>
        }
      >
        <Route index element={<PlatformPage />} />
      </Route>
      <Route
        path="/app"
        element={
          <RequireFirm>
            <AppLayout />
          </RequireFirm>
        }
      >
        <Route index element={<FirmAppHome />} />
        <Route
          path="reconciliation"
          element={
            <RequirePermission permission="reconciliation.access">
              <ComingSoonPage title="GSTR-2B Reconciliation" />
            </RequirePermission>
          }
        />
        <Route
          path="cases"
          element={
            <RequirePermission permission="cases.access">
              <ReconciliationCasesPage />
            </RequirePermission>
          }
        />
        <Route
          path="cases/new"
          element={
            <RequirePermission permission="cases.manage">
              <ReconciliationCaseFormPage />
            </RequirePermission>
          }
        />
        <Route
          path="cases/:id/edit"
          element={
            <RequirePermission permission="cases.manage">
              <ReconciliationCaseFormPage />
            </RequirePermission>
          }
        />
        <Route
          path="cases/:id"
          element={
            <RequirePermission permission="cases.access">
              <ReconciliationCaseDetailPage />
            </RequirePermission>
          }
        />
        <Route
          path="clients"
          element={
            <RequirePermission permission="clients.access">
              <ClientsPage />
            </RequirePermission>
          }
        />
        <Route
          path="data-mapping/master-fields"
          element={
            <RequirePermission permission="data_mapping.access">
              <MasterFieldsPage />
            </RequirePermission>
          }
        />
        <Route
          path="data-mapping/purchase-register"
          element={
            <RequirePermission permission="data_mapping.access">
              <PurchaseRegisterMappingsPage />
            </RequirePermission>
          }
        />
        <Route
          path="data-mapping/purchase-register/new"
          element={
            <RequirePermission permission="data_mapping.manage">
              <PurchaseRegisterMappingFormPage />
            </RequirePermission>
          }
        />
        <Route
          path="data-mapping/purchase-register/:id/edit"
          element={
            <RequirePermission permission="data_mapping.manage">
              <PurchaseRegisterMappingFormPage />
            </RequirePermission>
          }
        />
        <Route
          path="data-mapping/gstr-2b"
          element={
            <RequirePermission permission="data_mapping.access">
              <Gstr2bMappingsPage />
            </RequirePermission>
          }
        />
        <Route
          path="data-mapping/gstr-2b/new"
          element={
            <RequirePermission permission="data_mapping.manage">
              <Gstr2bMappingFormPage />
            </RequirePermission>
          }
        />
        <Route
          path="data-mapping/gstr-2b/:id/edit"
          element={
            <RequirePermission permission="data_mapping.manage">
              <Gstr2bMappingFormPage />
            </RequirePermission>
          }
        />
        <Route path="data-mapping" element={<Navigate to="/app/data-mapping/master-fields" replace />} />
        <Route
          path="settings"
          element={
            <RequirePermission permission="settings.access">
              <SettingsLayout />
            </RequirePermission>
          }
        >
          <Route index element={<FirmSettingsPage />} />
          <Route
            path="role-permissions"
            element={
              <RequireTenantAdmin>
                <RolePermissionsPage />
              </RequireTenantAdmin>
            }
          />
        </Route>
        <Route
          path="team"
          element={
            <RequirePermission permission="team.view">
              <TeamPage />
            </RequirePermission>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
