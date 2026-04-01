import { createContext, useState, useContext, type ReactNode } from "react";
import {
  TOKEN_STORAGE_KEY,
  USER_EMAIL_KEY,
  IS_ADMIN_KEY,
  decodeJWT,
} from "../utils/authUtils";
import { apiGet } from "../utils/api";
import { debugLog } from "../utils/debugLog";

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  userEmail: string | null;
  isAdmin: boolean;
  login: (token: string, email?: string) => Promise<void>;
  logout: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem(TOKEN_STORAGE_KEY)
  );
  const [userEmail, setUserEmail] = useState<string | null>(
    localStorage.getItem(USER_EMAIL_KEY)
  );
  const [isAdmin, setIsAdmin] = useState<boolean>(
    localStorage.getItem(IS_ADMIN_KEY) === "true"
  );

  const isAuthenticated = Boolean(token);

  const login = async (newToken: string, email?: string): Promise<void> => {
    // Store token in localStorage so apiGet can authenticate the /auth/me call.
    // We do NOT call setToken yet — isAuthenticated stays false until we confirm the role.
    localStorage.setItem(TOKEN_STORAGE_KEY, newToken);

    const extractedEmail = email || decodeJWT(newToken);
    if (extractedEmail) {
      localStorage.setItem(USER_EMAIL_KEY, extractedEmail);
    }

    try {
      const me = await apiGet<{ email: string; is_admin: boolean }>("/auth/me");
      const adminStatus = me.is_admin;

      localStorage.setItem(IS_ADMIN_KEY, String(adminStatus));
      setToken(newToken);
      if (extractedEmail) setUserEmail(extractedEmail);
      setIsAdmin(adminStatus);
    } catch {
      // /auth/me failed — we cannot determine the user's role.
      // Clean up and prevent login from completing.
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_EMAIL_KEY);
      localStorage.removeItem(IS_ADMIN_KEY);
      throw new Error("Failed to verify user role. Please try again.");
    }
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);
    localStorage.removeItem(IS_ADMIN_KEY);
    setToken(null);
    setUserEmail(null);
    setIsAdmin(false);
  };

  return (
    <AuthContext.Provider
      value={{ token, isAuthenticated, userEmail, isAdmin, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  // #region agent log
  debugLog("AuthContext.tsx:useAuth:ENTRY", "useAuth hook called", {}, "A");
  // #endregion
  const context = useContext(AuthContext);
  // #region agent log
  debugLog("AuthContext.tsx:useAuth:CONTEXT_CHECK", "Context check result", { isUndefined: context === undefined, hasToken: !!context?.token, hasUserEmail: !!context?.userEmail }, "A");
  // #endregion
  if (context === undefined) {
    // #region agent log
    debugLog("AuthContext.tsx:useAuth:ERROR", "useAuth called outside AuthProvider", {}, "A");
    // #endregion
    throw new Error("useAuth must be used within an AuthProvider");
  }
  // #region agent log
  debugLog("AuthContext.tsx:useAuth:SUCCESS", "useAuth returning context", { isAuthenticated: context.isAuthenticated, hasUserEmail: !!context.userEmail }, "A");
  // #endregion
  return context;
}
