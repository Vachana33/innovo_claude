import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";
import { AuthProvider } from "./contexts/AuthContext";
import { debugLog } from "./utils/debugLog";

// #region agent log - Global error handler
window.addEventListener('error', (event) => {
  debugLog("main.tsx:globalError", "Global error caught", { message: event.message, filename: event.filename, lineno: event.lineno, colno: event.colno, error: String(event.error) }, "E");
});
window.addEventListener('unhandledrejection', (event) => {
  debugLog("main.tsx:unhandledRejection", "Unhandled promise rejection", { reason: String(event.reason) }, "E");
});
// #endregion

// #region agent log
debugLog("main.tsx:ENTRY", "App starting", {}, "E");
// #endregion

try {
  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </React.StrictMode>
  );
  // #region agent log
  debugLog("main.tsx:SUCCESS", "App rendered successfully", {}, "E");
  // #endregion
} catch (error) {
  // #region agent log
  debugLog("main.tsx:ERROR", "App render failed", { error: String(error), errorType: error instanceof Error ? error.constructor.name : 'unknown', errorMessage: error instanceof Error ? error.message : 'no message', stack: error instanceof Error ? error.stack : 'no stack' }, "E");
  // #endregion
  throw error;
}
