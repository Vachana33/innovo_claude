import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage/LoginPage";
import DashboardPage from "./pages/DashboardPage/DashboardPage";
import FundingProgramsPage from "./pages/FundingProgramsPage/FundingProgramsPage";
import CompaniesPage from "./pages/CompaniesPage/CompaniesPage";
import DocumentsPage from "./pages/DocumentsPage/DocumentsPage";
import TemplatesPage from "./pages/TemplatesPage/TemplatesPage";
import AlteVorhabensbeschreibungPage from "./pages/AlteVorhabensbeschreibungPage/AlteVorhabensbeschreibungPage";
import EditorPage from "./pages/EditorPage/EditorPage";
import TemplateEditorPage from "./pages/TemplateEditorPage/TemplateEditorPage";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout/Layout";
import { debugLog } from "./utils/debugLog";

function App() {
  // #region agent log
  debugLog("App.tsx:App:ENTRY", "App component rendering", { pathname: window.location.pathname }, "E");
  // #endregion
  return (
    <Routes>
      {/* Public route - login page */}
      <Route path="/login" element={<LoginPage />} />
      
      {/* Protected routes with Layout - main navigation pages */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Layout>
              <DashboardPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/funding-programs"
        element={
          <ProtectedRoute>
            <Layout>
              <FundingProgramsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/companies"
        element={
          <ProtectedRoute>
            <Layout>
              <CompaniesPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <Layout>
              <DocumentsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/templates"
        element={
          <ProtectedRoute>
            <Layout>
              <TemplatesPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/alte-vorhabensbeschreibung"
        element={
          <ProtectedRoute>
            <Layout>
              <AlteVorhabensbeschreibungPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      
      {/* Protected routes without Layout - editor pages */}
      <Route
        path="/editor/:companyId/:docType"
        element={
          <ProtectedRoute>
            <EditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/templates/new"
        element={
          <ProtectedRoute>
            <TemplateEditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/templates/:id/edit"
        element={
          <ProtectedRoute>
            <TemplateEditorPage />
          </ProtectedRoute>
        }
      />
      
      {/* Default redirect to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
