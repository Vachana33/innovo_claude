import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { apiGet, apiDelete } from "../../utils/api";
import { debugLog } from "../../utils/debugLog";
import styles from "./DocumentsPage.module.css";

type Company = {
  id: number;
  name: string;
  website?: string;
};

type FundingProgram = {
  id: number;
  title: string;
};

type DocumentListItem = {
  id: number;
  company_id: number;
  company_name: string;
  funding_program_id?: number;
  funding_program_title?: string;
  type: string;
  title?: string | null;
  updated_at: string;
};

type Document = {
  id: number;
  company_id: number;
  funding_program_id?: number;
  type: string;
  title?: string | null;
  updated_at: string;
  company?: Company;
  funding_program?: FundingProgram;
};

export default function DocumentsPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [fundingPrograms, setFundingPrograms] = useState<FundingProgram[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);

  const [formTitle, setFormTitle] = useState("");
  const [formCompanyId, setFormCompanyId] = useState<number | null>(null);
  const [formProgramId, setFormProgramId] = useState<number | null>(null);
  const [formTemplate, setFormTemplate] = useState<string>("");
  const [formTemplateType, setFormTemplateType] = useState<"system" | "user" | "">("");
  const [availableTemplates, setAvailableTemplates] = useState<{system: Array<{id: string; name: string}>; user: Array<{id: string; name: string; description?: string}>}>({system: [], user: []});

  // Fetch data
  useEffect(() => {
    async function fetchData() {
      // #region agent log
      debugLog("DocumentsPage.tsx:fetchData:ENTRY", "Starting data fetch", {}, "D");
      // #endregion
      try {
        setIsLoading(true);
        // #region agent log
        debugLog("DocumentsPage.tsx:fetchData:BEFORE_API", "About to call APIs", {}, "D");
        // #endregion
        const [documentsData, companiesData, programsData, templatesData] = await Promise.all([
          apiGet<DocumentListItem[]>("/documents"),
          apiGet<Company[]>("/companies"),
          apiGet<FundingProgram[]>("/funding-programs"),
          apiGet<{system: Array<{id: string; name: string}>; user: Array<{id: string; name: string; description?: string}>}>("/templates/list"),
        ]);
        
        // #region agent log
        debugLog("DocumentsPage.tsx:fetchData:AFTER_API", "API calls completed", { documentsCount: documentsData?.length || 0, companiesCount: companiesData?.length || 0, programsCount: programsData?.length || 0, templatesCount: (templatesData?.system?.length || 0) + (templatesData?.user?.length || 0) }, "D");
        // #endregion
        
        // Map DocumentListItem to Document format for display
        const mappedDocuments: Document[] = documentsData.map((doc) => ({
          id: doc.id,
          company_id: doc.company_id,
          funding_program_id: doc.funding_program_id,
          type: doc.type,
          title: doc.title ?? undefined,
          updated_at: doc.updated_at,
          company: {
            id: doc.company_id,
            name: doc.company_name,
          },
          funding_program: doc.funding_program_id && doc.funding_program_title
            ? {
                id: doc.funding_program_id,
                title: doc.funding_program_title,
              }
            : undefined,
        }));
        
        // #region agent log
        debugLog("DocumentsPage.tsx:fetchData:BEFORE_SET_STATE", "About to set state", { mappedCount: mappedDocuments.length }, "D");
        // #endregion
        setDocuments(mappedDocuments);
        setCompanies(companiesData);
        setFundingPrograms(programsData);
        setAvailableTemplates({
          system: templatesData?.system ?? [],
          user: templatesData?.user ?? [],
        });
        // #region agent log
        debugLog("DocumentsPage.tsx:fetchData:SUCCESS", "Data fetch succeeded", {}, "D");
        // #endregion
      } catch (error: unknown) {
        // #region agent log
        debugLog("DocumentsPage.tsx:fetchData:ERROR", "Data fetch error", { error: String(error), errorType: error instanceof Error ? error.constructor.name : 'unknown', errorMessage: error instanceof Error ? error.message : 'no message' }, "D");
        // #endregion
        console.error("Error fetching data:", error);
        if (error instanceof Error && (error.message.includes("Authentication required") || error.message === "AUTH_EXPIRED")) {
          logout();
        }
      } finally {
        setIsLoading(false);
      }
    }
    fetchData();
  }, [logout]);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside() {
      if (openMenuId !== null) setOpenMenuId(null);
    }
    if (openMenuId !== null) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  }, [openMenuId]);

  // Filter documents
  const filteredDocuments = documents.filter((d) => {
    if (!searchTerm.trim()) return true;
    const searchLower = searchTerm.toLowerCase();
    return (
      d.company?.name.toLowerCase().includes(searchLower) ||
      d.funding_program?.title.toLowerCase().includes(searchLower) ||
      (d.title && d.title.toLowerCase().includes(searchLower)) ||
      formTitle.toLowerCase().includes(searchLower)
    );
  });

  // Create document draft
  async function handleCreateDraft(e: React.FormEvent) {
    e.preventDefault();
    if (!formTitle.trim() || !formCompanyId) return;

    // When a template is selected, a funding program is required so the backend applies the template
    if (formTemplate && !formProgramId) {
      alert("Please select a funding program to use a template. The template will be applied to the document.");
      return;
    }

    setIsCreating(true);
    try {
      // Navigate to editor which will create the document
      const docType = "vorhaben"; // Default to vorhabensbeschreibung
      const params = new URLSearchParams();
      if (formProgramId) {
        params.append("funding_program_id", formProgramId.toString());
      }
      if (formTemplate) {
        // Check if it's a UUID (user template) or system template name
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (uuidRegex.test(formTemplate)) {
          params.append("template_id", formTemplate);
        } else {
          params.append("template_name", formTemplate);
        }
      }
      if (formTitle.trim()) {
        params.append("title", formTitle.trim());
      }
      const queryString = params.toString();
      const url = `/editor/${formCompanyId}/${docType}${queryString ? `?${queryString}` : ""}`;
      navigate(url);
    } catch (error: unknown) {
      console.error("Error creating document:", error);
      alert(error instanceof Error ? error.message : "Failed to create document");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsCreating(false);
    }
  }

  // Format date
  function formatDate(dateString: string) {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  // Get document type display name
  function getDocumentTypeDisplay(type: string) {
    if (type === "vorhabensbeschreibung") return "Vorhabensbeschreibung";
    if (type === "vorkalkulation") return "Vorkalkulation";
    return type;
  }

  // Delete document
  async function handleDeleteDocument(doc: Document) {
    if (!confirm("Delete this document? This cannot be undone.")) return;
    try {
      await apiDelete(`/documents/${doc.id}`);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (error: unknown) {
      console.error("Error deleting document:", error);
      alert(error instanceof Error ? error.message : "Failed to delete document");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    }
  }

  return (
    <div className={styles.container} data-testid="page-documents">
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Documents</h1>
          <p className={styles.subtitle}>
            Manage and generate grant proposals.
          </p>
        </div>
        <button
          data-testid="documents-new-btn"
          onClick={() => {
            setFormTitle("");
            setFormCompanyId(null);
            setFormProgramId(null);
            setFormTemplate("");
            setShowCreateDialog(true);
          }}
          className={styles.newButton}
        >
          + New Document
        </button>
      </header>

      <div className={styles.searchBar}>
        <input
          data-testid="documents-search"
          type="text"
          placeholder="Search documents..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className={styles.searchInput}
        />
      </div>

      <div className={styles.documentsList} data-testid="documents-list">
        {isLoading ? (
          <div className={styles.loading} data-testid="documents-loading">Loading documents...</div>
        ) : filteredDocuments.length === 0 ? (
          <div className={styles.empty} data-testid="documents-empty">
            {documents.length === 0
              ? "No documents found. Create your first document!"
              : `No documents match "${searchTerm}"`}
          </div>
        ) : (
          filteredDocuments.map((doc) => (
            <div key={doc.id} className={styles.documentCard} data-testid="document-card">
              <div className={styles.cardIcon}>📄</div>
              <div className={styles.cardContent}>
                <div className={styles.cardHeader}>
                  <h3 className={styles.cardTitle}>
                    {doc.title || doc.company?.name || `Document ${doc.id}`}
                  </h3>
                  <div className={styles.cardActions}>
                    <button
                      data-testid={`document-menu-${doc.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenMenuId(openMenuId === doc.id ? null : doc.id);
                      }}
                      className={styles.menuButton}
                      title="More options"
                    >
                      ⋮
                    </button>
                    {openMenuId === doc.id && (
                      <div className={styles.menuDropdown} data-testid={`document-menu-dropdown-${doc.id}`}>
                        <button
                          data-testid={`document-edit-${doc.id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            const docType = doc.type === "vorhabensbeschreibung" ? "vorhaben" : "vorkalkulation";
                            const params = new URLSearchParams();
                            params.set("document_id", String(doc.id));
                            if (doc.funding_program_id) {
                              params.set("funding_program_id", String(doc.funding_program_id));
                            }
                            const qs = params.toString();
                            navigate(`/editor/${doc.company_id}/${docType}?${qs}`);
                            setOpenMenuId(null);
                          }}
                          className={styles.menuItem}
                        >
                          Edit
                        </button>
                        <button
                          data-testid={`document-delete-${doc.id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteDocument(doc);
                            setOpenMenuId(null);
                          }}
                          className={styles.menuItem}
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <p className={styles.cardProgram}>
                  {doc.funding_program?.title ?? "—"}
                </p>
                <div className={styles.cardMeta}>
                  <span>{getDocumentTypeDisplay(doc.type)}</span>
                  <span>•</span>
                  <span>{formatDate(doc.updated_at)}</span>
                  <span className={styles.draftBadge}>Draft</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create Document Dialog */}
      {showCreateDialog && (
        <div
          className={styles.dialogOverlay}
          data-testid="document-create-dialog-overlay"
          onClick={() => {
            setShowCreateDialog(false);
            setFormTitle("");
            setFormCompanyId(null);
            setFormProgramId(null);
            setFormTemplate("");
          }}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
            data-testid="document-create-dialog"
          >
            <div className={styles.dialogHeader}>
              <h3 className={styles.dialogTitle}>Create Document Draft</h3>
              <button
                data-testid="document-create-dialog-close"
                onClick={() => {
                  setShowCreateDialog(false);
                  setFormTitle("");
                  setFormCompanyId(null);
                  setFormProgramId(null);
                  setFormTemplate("");
                }}
                className={styles.closeButton}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleCreateDraft} data-testid="document-create-form">
              <label className={styles.formLabel}>
                Document Title
              </label>
              <input
                data-testid="document-create-title"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                className={styles.formInput}
                placeholder="e.g. Acme Corp - Innovation Grant"
              />
              <label className={styles.formLabel}>
                Company <span className={styles.required}>*</span>
              </label>
              <select
                data-testid="document-create-company"
                value={formCompanyId || ""}
                onChange={(e) => setFormCompanyId(e.target.value ? Number(e.target.value) : null)}
                required
                className={styles.formSelect}
              >
                <option value="">Select company</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <label className={styles.formLabel}>
                Funding Program
              </label>
              <select
                data-testid="document-create-program"
                value={formProgramId || ""}
                onChange={(e) => setFormProgramId(e.target.value ? Number(e.target.value) : null)}
                className={styles.formSelect}
              >
                <option value="">Select program</option>
                {fundingPrograms.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
              {formTemplateType && (
                <p className={styles.formHint}>
                  Select a funding program above to apply the template to your document.
                </p>
              )}
              <label className={styles.formLabel}>
                Template
              </label>
              <select
                value={formTemplateType}
                onChange={(e) => {
                  setFormTemplateType(e.target.value as "system" | "user" | "");
                  setFormTemplate(""); // Reset template selection when type changes
                }}
                className={styles.formSelect}
                style={{ marginBottom: formTemplateType ? "0.5rem" : "0" }}
              >
                <option value="">No template (use default)</option>
                <option value="system">System Template</option>
                <option value="user">My Templates</option>
              </select>
              {formTemplateType && (
                <select
                  value={formTemplate}
                  onChange={(e) => setFormTemplate(e.target.value)}
                  className={styles.formSelect}
                >
                  <option value="">Select a template...</option>
                  {formTemplateType === "system" && availableTemplates.system.length > 0 ? (
                    availableTemplates.system.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))
                  ) : formTemplateType === "system" ? (
                    <option value="" disabled>No system templates available</option>
                  ) : null}
                  {formTemplateType === "user" && availableTemplates.user.length > 0 ? (
                    availableTemplates.user.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} {t.description ? `- ${t.description}` : ""}
                      </option>
                    ))
                  ) : formTemplateType === "user" ? (
                    <option value="" disabled>No user templates available</option>
                  ) : null}
                </select>
              )}
              <div className={styles.dialogActions}>
                <button
                  type="button"
                  data-testid="document-create-cancel"
                  onClick={() => {
                    setShowCreateDialog(false);
                    setFormTitle("");
                    setFormCompanyId(null);
                    setFormProgramId(null);
                    setFormTemplate("");
                    setFormTemplateType("");
                  }}
                  className={styles.cancelButton}
                  disabled={isCreating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="document-create-submit"
                  className={styles.submitButton}
                  disabled={isCreating || !formCompanyId}
                >
                  {isCreating ? "Creating..." : "Create Draft"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
