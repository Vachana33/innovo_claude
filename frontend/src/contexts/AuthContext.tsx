import { createContext, useState, useContext, type ReactNode } from "react";
import {
  TOKEN_STORAGE_KEY,
  USER_EMAIL_KEY,
  decodeJWT,
} from "../utils/authUtils";
import { debugLog } from "../utils/debugLog";

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  userEmail: string | null;
  login: (token: string, email?: string) => void;
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

  const isAuthenticated = Boolean(token);

  const login = (newToken: string, email?: string) => {
    localStorage.setItem(TOKEN_STORAGE_KEY, newToken);
    setToken(newToken);

    const extractedEmail = email || decodeJWT(newToken);
    if (extractedEmail) {
      localStorage.setItem(USER_EMAIL_KEY, extractedEmail);
      setUserEmail(extractedEmail);
    }
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);
    setToken(null);
    setUserEmail(null);
  };

  return (
    <AuthContext.Provider
      value={{ token, isAuthenticated, userEmail, login, logout }}
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
