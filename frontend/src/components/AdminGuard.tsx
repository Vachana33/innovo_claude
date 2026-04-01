import { Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import type { ReactNode } from "react";

interface AdminGuardProps {
  children: ReactNode;
}

/**
 * Redirects non-admin users to /dashboard silently.
 * Must be placed inside ProtectedRoute (authentication is checked first).
 * The only source of truth for admin status is AuthContext.isAdmin,
 * which is populated from GET /auth/me on login.
 */
export default function AdminGuard({ children }: AdminGuardProps) {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}
