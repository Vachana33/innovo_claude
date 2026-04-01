import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage/LoginPage";
import DashboardPage from "./pages/DashboardPage/DashboardPage";
import NewProjectPage from "./pages/NewProjectPage/NewProjectPage";
import ProjectWorkspacePage from "./pages/ProjectWorkspacePage/ProjectWorkspacePage";
import FundingProgramsPage from "./pages/FundingProgramsPage/FundingProgramsPage";
import CompaniesPage from "./pages/CompaniesPage/CompaniesPage";
import DocumentsPage from "./pages/DocumentsPage/DocumentsPage";
import TemplatesPage from "./pages/TemplatesPage/TemplatesPage";
import AlteVorhabensbeschreibungPage from "./pages/AlteVorhabensbeschreibungPage/AlteVorhabensbeschreibungPage";
import EditorPage from "./pages/EditorPage/EditorPage";
import TemplateEditorPage from "./pages/TemplateEditorPage/TemplateEditorPage";
import KnowledgeBaseAdminPage from "./pages/KnowledgeBaseAdminPage/KnowledgeBaseAdminPage";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminGuard from "./components/AdminGuard";
import Layout from "./components/Layout/Layout";
import ProjectShell from "./components/ProjectShell/ProjectShell";
import { debugLog } from "./utils/debugLog";

function App() {
  // #region agent log
  debugLog("App.tsx:App:ENTRY", "App component rendering", { pathname: window.location.pathname }, "E");
  // #endregion
  return (
    <Routes>
      {/* Public route - login page */}
      <Route path="/login" element={<LoginPage />} />
      
      {/* Project shell routes — three-column shell (icon rail + project list + content) */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <ProjectShell>
              <DashboardPage />
            </ProjectShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/funding-programs"
        element={
          <ProtectedRoute>
            <AdminGuard>
              <Layout>
                <FundingProgramsPage />
              </Layout>
            </AdminGuard>
          </ProtectedRoute>
        }
      />
      <Route
        path="/companies"
        element={
          <ProtectedRoute>
            <AdminGuard>
              <Layout>
                <CompaniesPage />
              </Layout>
            </AdminGuard>
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
            <AdminGuard>
              <Layout>
                <AlteVorhabensbeschreibungPage />
              </Layout>
            </AdminGuard>
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
      
      {/* v2 Project routes */}
      <Route
        path="/projects/new"
        element={
          <ProtectedRoute>
            <NewProjectPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id"
        element={
          <ProtectedRoute>
            <ProjectShell>
              <ProjectWorkspacePage />
            </ProjectShell>
          </ProtectedRoute>
        }
      />

      {/* Admin routes — not in primary navigation */}
      <Route
        path="/admin/knowledge-base"
        element={
          <ProtectedRoute>
            <AdminGuard>
              <Layout>
                <KnowledgeBaseAdminPage />
              </Layout>
            </AdminGuard>
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
