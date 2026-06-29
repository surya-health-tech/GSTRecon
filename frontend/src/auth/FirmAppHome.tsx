import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { defaultFirmHomePath } from "./permissions";

/** Firm app index: send the user to the first module they may access (not always Dashboard). */
export function FirmAppHome() {
  const { me, loading } = useAuth();
  if (loading) return null;
  return <Navigate to={defaultFirmHomePath(me?.permissions)} replace />;
}
