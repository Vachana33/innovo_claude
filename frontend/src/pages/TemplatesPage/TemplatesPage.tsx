import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { apiGet, apiPost, apiDelete } from "../../utils/api";
import { devIngest } from "../../utils/debugLog";
import styles from "./TemplatesPage.module.css";

type SystemTemplate = {
  id: string;
  name: string;
  source: "system";
};

type UserTemplate = {
  id: string;
  name: string;
  description?: string;
  source: "user";
};

export default function TemplatesPage() {
  // #region agent log (dev only - no ingest in production)
  devIngest({ location: "TemplatesPage.tsx:25", message: "TemplatesPage component rendering", data: {}, timestamp: Date.now(), runId: "initial", hypothesisId: "A" });
  // #endregion

  const navigate = useNavigate();
  const { logout } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [systemTemplates, setSystemTemplates] = useState<SystemTemplate[]>([]);
  const [userTemplates, setUserTemplates] = useState<UserTemplate[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [isDuplicating, setIsDuplicating] = useState(false);

  async function fetchTemplates() {
    try {
      setIsLoading(true);
      const response = await apiGet<{
        system: Array<{ id: string; name: string; source: string }>;
        user: Array<{ id: string; name: string; source: string; description?: string }>;
      }>("/templates/list");
      setSystemTemplates((response.system || []) as SystemTemplate[]);
      setUserTemplates((response.user || []) as UserTemplate[]);
    } catch (error: unknown) {
      console.error("Error fetching templates:", error);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsLoading(false);
    }
  }

  // Fetch templates on mount
  useEffect(() => {
    fetchTemplates();
  }, [logout]);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside() {
      if (openMenuId !== null) {
        setOpenMenuId(null);
      }
    }
    if (openMenuId !== null) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  }, [openMenuId]);

  // Filter templates
  const filteredSystemTemplates = systemTemplates.filter((t) => {
    if (!searchTerm.trim()) return true;
    const searchLower = searchTerm.toLowerCase();
    return t.name.toLowerCase().includes(searchLower);
  });

  const filteredUserTemplates = userTemplates.filter((t) => {
    if (!searchTerm.trim()) return true;
    const searchLower = searchTerm.toLowerCase();
    return (
      t.name.toLowerCase().includes(searchLower) ||
      (t.description && t.description.toLowerCase().includes(searchLower))
    );
  });

  // Copy template content
  async function handleCopyContent(template: SystemTemplate | UserTemplate) {
    // #region agent log (dev only)
    devIngest({ location: "TemplatesPage.tsx:85", message: "Copying template content", data: { templateId: template.id, source: template.source }, timestamp: Date.now(), runId: "initial", hypothesisId: "A" });
    // #endregion

    try {
      let templateData: { sections: any[] };
      
      if (template.source === "system") {
        // Fetch system template structure
        const response = await apiGet<{ sections: any[] }>(`/templates/system/${template.id}`);
        templateData = response;
      } else {
        // Fetch user template
        const response = await apiGet<{
          id: string;
          name: string;
          description?: string;
          template_structure: { sections: any[] };
        }>(`/user-templates/${template.id}`);
        templateData = response.template_structure;
      }

      // Serialize sections to JSON
      const jsonContent = JSON.stringify(templateData.sections, null, 2);
      
      // Copy to clipboard
      await navigator.clipboard.writeText(jsonContent);
      alert("Template content copied to clipboard!");
    } catch (error: unknown) {
      console.error("Error copying template:", error);
      // #region agent log (dev only)
      devIngest({ location: "TemplatesPage.tsx:110", message: "Error copying template", data: { error: error instanceof Error ? error.message : String(error) }, timestamp: Date.now(), runId: "initial", hypothesisId: "A" });
      // #endregion
      alert(error instanceof Error ? error.message : "Failed to copy template content");
    }
  }

  // Duplicate user template
  async function handleDuplicate(templateId: string) {
    setIsDuplicating(true);
    setOpenMenuId(null);
    try {
      await apiPost<{ id: string; name: string }>(`/user-templates/duplicate/${templateId}`);
      await fetchTemplates();
    } catch (error: unknown) {
      console.error("Error duplicating template:", error);
      const message =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Failed to duplicate template";
      alert(message);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsDuplicating(false);
    }
  }

  // Delete user template
  async function handleDelete() {
    if (!deletingId) return;

    setIsDeleting(true);
    try {
      await apiDelete(`/user-templates/${deletingId}`);
      setUserTemplates((prev) => prev.filter((t) => t.id !== deletingId));
      setDeletingId(null);
    } catch (error: unknown) {
      console.error("Error deleting template:", error);
      alert(error instanceof Error ? error.message : "Failed to delete template");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsDeleting(false);
    }
  }

  // #region agent log (dev only)
  devIngest({ location: "TemplatesPage.tsx:135", message: "Rendering TemplatesPage", data: { systemCount: systemTemplates.length, userCount: userTemplates.length, isLoading }, timestamp: Date.now(), runId: "initial", hypothesisId: "A" });
  // #endregion

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Templates</h1>
          <p className={styles.subtitle}>
            Manage document templates for your projects.
          </p>
        </div>
        <button
          onClick={() => navigate("/templates/new")}
          className={styles.newButton}
        >
          + New Template
        </button>
      </header>

      <div className={styles.searchBar}>
        <input
          type="text"
          placeholder="Search templates..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className={styles.searchInput}
        />
      </div>

      {isLoading ? (
        <div className={styles.loading}>Loading templates...</div>
      ) : (
        <div className={styles.templatesGrid}>
          {/* System Templates */}
          {filteredSystemTemplates.map((template) => (
            <div key={template.id} className={styles.templateCard}>
              <div className={styles.cardHeader}>
                <div className={styles.cardIcon}>📋</div>
                <div className={styles.cardTitleSection}>
                  <h3 className={styles.cardTitle}>{template.name}</h3>
                  <span className={styles.systemLabel}>System Template</span>
                </div>
              </div>
              <div className={styles.cardActions}>
                <button
                  onClick={() => handleCopyContent(template)}
                  className={styles.copyButton}
                >
                  <span className={styles.copyIcon}>📋</span>
                  Copy Content
                </button>
              </div>
            </div>
          ))}

          {/* User Templates */}
          {filteredUserTemplates.map((template) => (
            <div key={template.id} className={styles.templateCard}>
              <div className={styles.cardHeader}>
                <div className={styles.cardIcon}>📝</div>
                <div className={styles.cardTitleSection}>
                  <h3 className={styles.cardTitle}>{template.name}</h3>
                  {template.description && (
                    <p className={styles.cardDescription}>{template.description}</p>
                  )}
                </div>
                <div className={styles.cardActions}>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenuId(openMenuId === template.id ? null : template.id);
                    }}
                    className={styles.menuButton}
                    title="More options"
                    disabled={isDuplicating}
                  >
                    ⋮
                  </button>
                  {openMenuId === template.id && (
                    <div className={styles.menuDropdown} onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className={styles.menuItem}
                        onClick={() => {
                          setOpenMenuId(null);
                          navigate(`/templates/${template.id}/edit`);
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className={styles.menuItem}
                        onClick={() => handleDuplicate(template.id)}
                      >
                        Duplicate
                      </button>
                      <button
                        type="button"
                        className={styles.menuItem}
                        onClick={() => {
                          setDeletingId(template.id);
                          setOpenMenuId(null);
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {filteredSystemTemplates.length === 0 && filteredUserTemplates.length === 0 && (
            <div className={styles.empty}>
              {systemTemplates.length === 0 && userTemplates.length === 0
                ? "No templates found. Create your first template!"
                : `No templates match "${searchTerm}"`}
            </div>
          )}
        </div>
      )}

      {/* Delete Confirmation */}
      {deletingId && (
        <div
          className={styles.dialogOverlay}
          onClick={() => setDeletingId(null)}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className={styles.dialogTitle}>Delete Template</h3>
            <p>Are you sure you want to delete this template? This action cannot be undone.</p>
            <div className={styles.dialogActions}>
              <button
                type="button"
                onClick={() => setDeletingId(null)}
                className={styles.cancelButton}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDelete}
                className={styles.deleteConfirmButton}
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
