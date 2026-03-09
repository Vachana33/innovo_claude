import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { apiPost } from "../../utils/api";
import styles from "./LoginPage.module.css";

import logo from "../../assets/innovo-logo.png";
import bgImage from "../../assets/login-bg.jpg";

function isValidEmail(email: string): boolean {
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!pattern.test(email)) return false;
  const emailLower = email.toLowerCase();
  // Explicitly allow donotreply@aiio.de
  if (emailLower === "donotreply@aiio.de") return true;
  // Allow emails ending with @innovo-consulting.de or @aiio.de
  return (
    emailLower.endsWith("@innovo-consulting.de") ||
    emailLower.endsWith("@aiio.de")
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  
  // Redirect if already authenticated
  // This prevents authenticated users from accessing login page
  // MUST be in useEffect to avoid updating BrowserRouter during render
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isAuthenticated, navigate]);
  
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Client-side validation
    if (!isValidEmail(email)) {
      setError(
        "Email must end with @innovo-consulting.de or @aiio.de"
      );
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setIsLoading(true);

    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const data = await apiPost<{ success?: boolean; access_token?: string; token?: string; message?: string }>(endpoint, {
        email: email.toLowerCase(),
        password: password,
      });

      // Handle success based on mode
      if (data.success) {
        if (mode === "login") {
          // Login successful - store token
          // Backend now returns TokenResponse with access_token
          if (data.access_token) {
            // Store token in context and localStorage
            // State update will trigger useEffect to navigate
            login(data.access_token, email.toLowerCase());
            setIsLoading(false);
            // Navigation will be handled by useEffect when isAuthenticated becomes true
          } else {
            setError("Login successful but no token received. Please try again.");
            setIsLoading(false);
          }
        } else {
          // Registration successful - show message, clear ALL fields, switch to login
          setSuccess("Account created successfully. Please log in with your credentials.");
          setEmail(""); // Clear email field
          setPassword(""); // Clear password field
          setMode("login"); // Switch to login mode
          setIsLoading(false);
        }
      } else {
        setError(data.message || "An error occurred. Please try again.");
        setIsLoading(false);
      }
    } catch (err: unknown) {
      // Network error or API error (apiPost throws on non-ok responses)
      const errorMessage = err instanceof Error ? err.message : "Network error. Please check if the backend server is running.";
      setError(errorMessage);
      setIsLoading(false);
    }
  }

  return (
    <div
      className={styles.container}
      style={{ backgroundImage: `url(${bgImage})` }}
      data-testid="login-page"
    >
      <img src={logo} alt="Innovo Logo" className={styles.logo} data-testid="login-logo" />

      <div className={styles.box} data-testid="login-box">
        <h1 className={styles.title} data-testid="login-title">Innovo Agent Login</h1>
        <p className={styles.subtitle}>
          Internal workspace for funding projects.
        </p>

        {/* Mode toggle */}
        <div className={styles.modeSwitch} data-testid="login-mode-switch">
          <button
            data-testid="login-tab"
            className={mode === "login" ? styles.activeTab : styles.inactiveTab}
            onClick={() => {
              setMode("login");
              setError(null);
              setSuccess(null);
            }}
          >
            Login
          </button>
          <button
            data-testid="signup-tab"
            className={mode === "signup" ? styles.activeTab : styles.inactiveTab}
            onClick={() => {
              setMode("signup");
              setError(null);
              setSuccess(null);
            }}
          >
            Create Account
          </button>
        </div>

        <form onSubmit={handleSubmit} data-testid="login-form">
          <label className={styles.label}>Email</label>
          <input
            data-testid="login-email"
            className={styles.input}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@innovo-consulting.de"
          />

          <label className={styles.label}>Password</label>
          <input
            data-testid="login-password"
            className={styles.input}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />

          {error && <p className={styles.error} data-testid="login-error">{error}</p>}
          {success && <p className={styles.success} data-testid="login-success">{success}</p>}

          <button 
            className={styles.submit} 
            type="submit"
            disabled={isLoading}
            data-testid="login-submit"
          >
            {isLoading 
              ? "Processing..." 
              : mode === "login" 
                ? "Login" 
                : "Create Account"
            }
          </button>
        </form>

        <p className={styles.note}>
          Only @innovo-consulting.de or @aiio.de emails are allowed.
        </p>
      </div>
    </div>
  );
}
