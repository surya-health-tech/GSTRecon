import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch, PF_SESSION_LOST } from "../api/http";

export type PlatformTenantAccessMe = {
  session_id: number;
  tenant_id: number;
  tenant_name: string;
  started_at: string;
  platform_admin_name: string;
  platform_admin_email: string | null;
};

export type Me = {
  id: number;
  email: string | null;
  full_name: string;
  login_method?: string;
  phone?: string | null;
  phone_country_code?: string | null;
  is_platform_super_admin: boolean;
  tenant_id: number | null;
  tenant_name: string | null;
  role: string | null;
  location_id?: number | null;
  permissions: Record<string, boolean> | null;
  platform_tenant_access?: PlatformTenantAccessMe | null;
};

type AuthState = {
  me: Me | null;
  loading: boolean;
  refreshMe: () => Promise<void>;
  login: (loginId: string, password: string) => Promise<void>;
  logout: () => void;
  startTenantPortal: (tenantId: number) => Promise<void>;
  endTenantPortal: () => Promise<void>;
  startingTenantPortal: boolean;
  endingTenantPortal: boolean;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

function storeTokens(access: string, refresh: string) {
  localStorage.setItem("pf_access_token", access);
  localStorage.setItem("pf_refresh_token", refresh);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [startingTenantPortal, setStartingTenantPortal] = useState(false);
  const [endingTenantPortal, setEndingTenantPortal] = useState(false);

  const refreshMe = useCallback(async () => {
    const token = localStorage.getItem("pf_access_token");
    if (!token) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      const data = await apiFetch<Me>("/auth/me");
      setMe(data);
    } catch {
      localStorage.removeItem("pf_access_token");
      localStorage.removeItem("pf_refresh_token");
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  useEffect(() => {
    const onSessionLost = () => {
      setMe(null);
      navigate("/?reason=expired", { replace: true });
    };
    window.addEventListener(PF_SESSION_LOST, onSessionLost);
    return () => window.removeEventListener(PF_SESSION_LOST, onSessionLost);
  }, [navigate]);

  const login = useCallback(
    async (loginId: string, password: string) => {
      const res = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ login_id: loginId, password }),
      });
      storeTokens(res.access_token, res.refresh_token);
      await refreshMe();
    },
    [refreshMe]
  );

  const logout = useCallback(() => {
    localStorage.removeItem("pf_access_token");
    localStorage.removeItem("pf_refresh_token");
    setMe(null);
    qc.clear();
    navigate("/", { replace: true });
  }, [navigate, qc]);

  const startTenantPortal = useCallback(
    async (tenantId: number) => {
      setStartingTenantPortal(true);
      try {
        const res = await apiFetch<{
          access_token: string;
          refresh_token: string;
          tenant_id: number;
          tenant_name: string;
        }>(`/platform/tenants/${tenantId}/tenant-access`, { method: "POST" });
        storeTokens(res.access_token, res.refresh_token);
        qc.clear();
        await refreshMe();
        navigate("/app", { replace: true });
      } finally {
        setStartingTenantPortal(false);
      }
    },
    [navigate, qc, refreshMe]
  );

  const endTenantPortal = useCallback(async () => {
    setEndingTenantPortal(true);
    try {
      const res = await apiFetch<{ access_token: string; refresh_token: string }>("/platform/tenant-access/end", {
        method: "POST",
      });
      storeTokens(res.access_token, res.refresh_token);
      qc.clear();
      await refreshMe();
      navigate("/platform", { replace: true });
    } finally {
      setEndingTenantPortal(false);
    }
  }, [navigate, qc, refreshMe]);

  const value = useMemo(
    () => ({
      me,
      loading,
      refreshMe,
      login,
      logout,
      startTenantPortal,
      endTenantPortal,
      startingTenantPortal,
      endingTenantPortal,
    }),
    [me, loading, refreshMe, login, logout, startTenantPortal, endTenantPortal, startingTenantPortal, endingTenantPortal]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function isPlatformTenantAccess(me: Me | null | undefined): boolean {
  return Boolean(me?.platform_tenant_access?.session_id);
}
