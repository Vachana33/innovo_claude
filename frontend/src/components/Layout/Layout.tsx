import type { ReactNode } from "react";

import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { debugLog } from "../../utils/debugLog";
import styles from "./Layout.module.css";
import logo from "../../assets/innovo-logo.png";

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  // #region agent log
  debugLog("Layout.tsx:Layout:ENTRY", "Layout component rendering", {}, "A");
  // #endregion
  const location = useLocation();
  const navigate = useNavigate();
  // #region agent log
  debugLog("Layout.tsx:Layout:BEFORE_USE_AUTH", "About to call useAuth", {}, "A");
  // #endregion
  const { logout, userEmail } = useAuth();
  // #region agent log
  debugLog("Layout.tsx:Layout:AFTER_USE_AUTH", "useAuth succeeded", { hasUserEmail: !!userEmail, userEmailLength: userEmail?.length || 0 }, "A");
  // #endregion

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const navItems = [
    { path: "/dashboard", label: "Dashboard", icon: "📊" },
    { path: "/funding-programs", label: "Funding Programs", icon: "💼" },
    { path: "/companies", label: "Companies", icon: "🏢" },
    { path: "/documents", label: "Documents", icon: "📄" },
    { path: "/templates", label: "Templates", icon: "📋" },
    { path: "/alte-vorhabensbeschreibung", label: "Alte Vorhabensbeschreibung", icon: "📜" },
  ];

  const isActive = (path: string) => {
    if (path === "/dashboard") {
      return location.pathname === "/dashboard";
    }
    return location.pathname.startsWith(path);
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (userEmail) {
      return userEmail.charAt(0).toUpperCase();
    }
    return "U";
  };

  // Truncate email for display
  const truncateEmail = (email: string, maxLength: number = 25) => {
    if (email.length <= maxLength) return email;
    return email.substring(0, maxLength - 3) + "...";
  };

  return (
    <div className={styles.container} data-testid="layout">
      {/* Sidebar */}
      <aside className={styles.sidebar} data-testid="layout-sidebar">
        {/* Logo and App Name */}
        <div className={styles.logoSection}>
          <img src={logo} alt="Innovo Logo" className={styles.logo} />
          <h1 className={styles.appName}>Innovo Agent</h1>
        </div>

        {/* Navigation Items */}
        <nav className={styles.nav} data-testid="layout-nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`${styles.navItem} ${
                isActive(item.path) ? styles.navItemActive : ""
              }`}
              data-testid={`nav-${item.path.slice(1)}`}
            >
              <span className={styles.navIcon}>{item.icon}</span>
              <span className={styles.navLabel}>{item.label}</span>
            </Link>
          ))}
        </nav>

        {/* User Profile Section */}
        <div className={styles.userSection} data-testid="layout-user-section">
          <div className={styles.userAvatar}>{getUserInitials()}</div>
          <div className={styles.userInfo}>
            <div className={styles.userName}>User</div>
            <div className={styles.userEmail}>
              {userEmail ? truncateEmail(userEmail) : "user@example.com"}
            </div>
          </div>
          <button
            onClick={handleLogout}
            className={styles.logoutButton}
            title="Log out"
            data-testid="logout-btn"
          >
            →
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className={styles.mainContent}>{children}</main>
    </div>
  );
}
