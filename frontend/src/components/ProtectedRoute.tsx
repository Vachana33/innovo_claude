/**
 * ProtectedRoute component - prevents unauthenticated access to protected pages.
 * 
 * Security: Redirects to /login if user is not authenticated.
 * This ensures users cannot access protected routes without a valid JWT token.
 */
import { Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuth();

  // If not authenticated, redirect to login page
  // The login page will handle authentication
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // User is authenticated, render the protected content
  return <>{children}</>;
}
