import { useState, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { apiGet, apiPost, apiPut, apiDelete, apiUploadFile, apiUploadFiles } from "../../utils/api";
import styles from "./CompaniesPage.module.css";

type Company = {
  id: number;
  name: string;
  website?: string;
  audio_path?: string;
  processing_status?: string;
  transcript_text?: string;
  transcript_raw?: string;
  transcript_clean?: string;
  created_at: string;
};

type CompanyDocument = {
  id: string;
  company_id: number;
  original_filename: string;
  file_type: string;
  file_size: number;
  has_extracted_text: boolean;
  uploaded_at: string;
};

export default function CompaniesPage() {
  const { logout } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [formName, setFormName] = useState("");
  const [formWebsite, setFormWebsite] = useState("");
  const [formAudio, setFormAudio] = useState<File | null>(null);
  const [formDocuments, setFormDocuments] = useState<File[]>([]);
  const [companyDocuments, setCompanyDocuments] = useState<Record<number, CompanyDocument[]>>({});
  const [isUploadingDocuments, setIsUploadingDocuments] = useState(false);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState<Record<number, boolean>>({});
  const [documentsToDelete, setDocumentsToDelete] = useState<Record<number, Set<string>>>({});
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [audioToRemove, setAudioToRemove] = useState(false);

  // Fetch companies
  useEffect(() => {
    async function fetchCompanies() {
      try {
        setIsLoading(true);
        const data = await apiGet<Company[]>("/companies");
        setCompanies(data);
      } catch (error: unknown) {
        console.error("Error fetching companies:", error);
        if (error instanceof Error && error.message.includes("Authentication required")) {
          logout();
        }
      } finally {
        setIsLoading(false);
      }
    }
    fetchCompanies();
  }, [logout]);

  // Filter companies
  const filteredCompanies = companies.filter((c) => {
    if (!searchTerm.trim()) return true;
    const searchLower = searchTerm.toLowerCase();
    return (
      c.name.toLowerCase().includes(searchLower) ||
      (c.website && c.website.toLowerCase().includes(searchLower))
    );
  });

  // Create company
  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formName.trim()) return;

    setIsCreating(true);
    try {
      let audioPath: string | undefined = undefined;
      if (formAudio) {
        const uploadData = await apiUploadFile("/upload-audio", formAudio) as { audio_path?: string };
        audioPath = uploadData.audio_path;
      }

      const created = await apiPost<Company>("/companies", {
        name: formName.trim(),
        website: formWebsite.trim() || undefined,
        audio_path: audioPath,
      });
      setCompanies((prev) => [created, ...prev]);
      setFormName("");
      setFormWebsite("");
      setFormAudio(null);
      setShowDialog(false);
    } catch (error: unknown) {
      console.error("Error creating company:", error);
      alert(error instanceof Error ? error.message : "Failed to create company");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsCreating(false);
    }
  }

  // Update company
  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId || !formName.trim()) return;

    setIsUpdating(true);
    try {
      let audioPath: string | null | undefined = undefined;
      if (formAudio) {
        const uploadData = await apiUploadFile("/upload-audio", formAudio) as { audio_path?: string };
        audioPath = uploadData.audio_path ?? null;
      } else if (audioToRemove) {
        audioPath = null;
      } else {
        const company = companies.find((c) => c.id === editingId);
        audioPath = company?.audio_path ?? null;
      }

      const updated = await apiPut<Company>(`/companies/${editingId}`, {
        name: formName.trim(),
        website: formWebsite.trim() || undefined,
        audio_path: audioPath ?? undefined,
      });
      setCompanies((prev) => prev.map((c) => (c.id === editingId ? updated : c)));
      
      // Delete documents that were marked for deletion
      if (editingId && documentsToDelete[editingId] && documentsToDelete[editingId].size > 0) {
        setIsUploadingDocuments(true);
        try {
          for (const docId of documentsToDelete[editingId]) {
            await apiDelete(`/companies/${editingId}/documents/${docId}`);
          }
        } catch (deleteError: unknown) {
          console.error("Error deleting documents:", deleteError);
          alert(deleteError instanceof Error ? deleteError.message : "Failed to delete some documents");
        } finally {
          setIsUploadingDocuments(false);
        }
      }
      
      // Upload documents if any were selected
      if (formDocuments.length > 0) {
        setIsUploadingDocuments(true);
        try {
          await apiUploadFiles(`/companies/${editingId}/documents/upload`, formDocuments);
        } catch (uploadError: unknown) {
          console.error("Error uploading documents:", uploadError);
          alert(uploadError instanceof Error ? uploadError.message : "Failed to upload documents");
        } finally {
          setIsUploadingDocuments(false);
        }
      }
      
      // Refresh documents list after updates
      if (editingId) {
        await fetchCompanyDocuments(editingId);
      }
      
      setEditingId(null);
      setFormName("");
      setFormWebsite("");
      setFormAudio(null);
      setFormDocuments([]);
      setAudioToRemove(false);
      if (editingId) {
        setDocumentsToDelete(prev => {
          const newState = { ...prev };
          delete newState[editingId];
          return newState;
        });
      }
      setShowDialog(false);
    } catch (error: unknown) {
      console.error("Error updating company:", error);
      alert(error instanceof Error ? error.message : "Failed to update company");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsUpdating(false);
    }
  }

  // Delete company
  async function handleDelete() {
    if (!deletingId) return;

    setIsDeleting(true);
    try {
      await apiDelete(`/companies/${deletingId}`);
      setCompanies((prev) => prev.filter((c) => c.id !== deletingId));
      setDeletingId(null);
    } catch (error: unknown) {
      console.error("Error deleting company:", error);
      alert(error instanceof Error ? error.message : "Failed to delete company");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsDeleting(false);
    }
  }

  // Fetch company documents
  async function fetchCompanyDocuments(companyId: number) {
    setIsLoadingDocuments((prev) => ({ ...prev, [companyId]: true }));
    try {
      const response = await apiGet<{ documents: CompanyDocument[] }>(`/companies/${companyId}/documents`);
      setCompanyDocuments((prev) => ({ ...prev, [companyId]: response.documents || [] }));
    } catch (error: unknown) {
      console.error("Error fetching documents:", error);
      setCompanyDocuments((prev) => ({ ...prev, [companyId]: [] }));
    } finally {
      setIsLoadingDocuments((prev) => ({ ...prev, [companyId]: false }));
    }
  }

  // Open edit dialog
  async function openEditDialog(company: Company) {
    setEditingId(company.id);
    setFormName(company.name);
    setFormWebsite(company.website || "");
    setFormAudio(null);
    setFormDocuments([]);
    setAudioToRemove(false);
    setDocumentsToDelete(prev => ({ ...prev, [company.id]: new Set() }));
    setShowDialog(true);
    // Fetch documents for this company
    await fetchCompanyDocuments(company.id);
  }

  // Toggle document deletion
  function toggleDocumentDelete(companyId: number, docId: string) {
    setDocumentsToDelete(prev => {
      const newSet = new Set(prev[companyId] || []);
      if (newSet.has(docId)) {
        newSet.delete(docId);
      } else {
        newSet.add(docId);
      }
      return { ...prev, [companyId]: newSet };
    });
  }

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

  return (
    <div className={styles.container} data-testid="page-companies">
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Companies</h1>
          <p className={styles.subtitle}>
            Manage company profiles and information.
          </p>
        </div>
        <button
          data-testid="companies-new-btn"
          onClick={() => {
            setEditingId(null);
            setFormName("");
            setFormWebsite("");
            setFormAudio(null);
            setShowDialog(true);
          }}
          className={styles.newButton}
        >
          + New Company
        </button>
      </header>

      <div className={styles.searchBar}>
        <input
          data-testid="companies-search"
          type="text"
          placeholder="Search companies..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className={styles.searchInput}
        />
      </div>

      <div className={styles.companiesGrid} data-testid="companies-list">
        {isLoading ? (
          <div className={styles.loading} data-testid="companies-loading">Loading companies...</div>
        ) : filteredCompanies.length === 0 ? (
          <div className={styles.empty} data-testid="companies-empty">
            {companies.length === 0
              ? "No companies found. Create your first company!"
              : `No companies match "${searchTerm}"`}
          </div>
        ) : (
          filteredCompanies.map((company) => (
            <div key={company.id} className={styles.companyCard} data-testid="company-card">
              <div className={styles.cardHeader}>
                <h3 className={styles.cardTitle}>{company.name}</h3>
                <p>{new Date(company.created_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}</p>
                <div className={styles.cardActions}>
                  <button
                    data-testid={`company-menu-${company.id}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenuId(openMenuId === company.id ? null : company.id);
                    }}
                    className={styles.menuButton}
                    title="More options"
                  >
                    ⋮
                  </button>
                  {openMenuId === company.id && (
                    <div className={styles.menuDropdown} data-testid={`company-menu-dropdown-${company.id}`}>
                      <button
                        data-testid={`company-edit-${company.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          openEditDialog(company);
                          setOpenMenuId(null);
                        }}
                        className={styles.menuItem}
                      >
                        Edit
                      </button>
                      <button
                        data-testid={`company-delete-${company.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingId(company.id);
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
              {company.website && (
                <a
                  href={company.website.startsWith('http') ? company.website : `https://${company.website}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.visitButton}
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className={styles.visitIcon}>🌐</span>
                  Visit Website
                </a>
              )}
              {company.audio_path && (
                <div className={styles.cardMeta}>
                  <span className={styles.metaIcon}>🎙️</span>
                  <span>
                    {company.processing_status === "processing" 
                      ? "Transcribing..." 
                      : company.processing_status === "done" && company.transcript_clean
                      ? "Transcript ready"
                      : company.processing_status === "failed"
                      ? "Transcription failed"
                      : "Audio file attached"}
                  </span>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Create/Edit Dialog */}
      {showDialog && (
        <div
          className={styles.dialogOverlay}
          data-testid="company-dialog-overlay"
          onClick={() => {
            setShowDialog(false);
            setEditingId(null);
            setFormName("");
            setFormWebsite("");
            setFormAudio(null);
            setAudioToRemove(false);
          }}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
            data-testid="company-dialog"
          >
            <h3 className={styles.dialogTitle}>
              {editingId ? "Edit Company" : "New Company"}
            </h3>
            <form onSubmit={editingId ? handleUpdate : handleCreate} data-testid="company-form">
              <label className={styles.formLabel}>
                Company Name <span className={styles.required}>*</span>
              </label>
              <input
                data-testid="company-form-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                required
                className={styles.formInput}
                placeholder="e.g. Acme Corporation"
              />
              <label className={styles.formLabel}>Website (optional)</label>
              <input
                data-testid="company-form-website"
                value={formWebsite}
                onChange={(e) => setFormWebsite(e.target.value)}
                className={styles.formInput}
                placeholder="https://..."
              />
              <label className={styles.formLabel}>Meeting Audio (optional)</label>
              {editingId && (() => {
                const company = companies.find((c) => c.id === editingId);
                if (!company?.audio_path) return null;
                const isMarkedForDelete = audioToRemove;
                return (
                  <div className={styles.fileList} style={{ marginBottom: "0.5rem" }}>
                    <div style={{ fontWeight: 500, marginBottom: "0.5rem" }}>Existing:</div>
                    <div
                      className={styles.fileItem}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: "0.5rem",
                        opacity: isMarkedForDelete ? 0.5 : 1,
                        textDecoration: isMarkedForDelete ? "line-through" : "none",
                      }}
                    >
                      <span>🎙️ Meeting audio attached</span>
                      <button
                        type="button"
                        onClick={() => setAudioToRemove((prev) => !prev)}
                        style={{
                          padding: "0.25rem 0.5rem",
                          border: "1px solid #dc3545",
                          backgroundColor: isMarkedForDelete ? "#dc3545" : "#fff",
                          color: isMarkedForDelete ? "#fff" : "#dc3545",
                          borderRadius: "4px",
                          cursor: "pointer",
                          fontSize: "0.75rem",
                        }}
                        title={isMarkedForDelete ? "Restore audio" : "Delete audio"}
                      >
                        {isMarkedForDelete ? "✓ Restore" : "🗑️ Delete"}
                      </button>
                    </div>
                  </div>
                );
              })()}
              <input
                type="file"
                accept="audio/*"
                onChange={(e) => setFormAudio(e.target.files?.[0] ?? null)}
                className={styles.formFile}
              />
              <label className={styles.formLabel}>Documents (optional)</label>
              {editingId && isLoadingDocuments[editingId] && (
                <div className={styles.loadingDocuments} style={{ marginBottom: "0.5rem" }}>
                  Loading documents...
                </div>
              )}
              {editingId && companyDocuments[editingId] && companyDocuments[editingId].length > 0 && (
                <div className={styles.fileList} style={{ marginBottom: "0.5rem" }}>
                  <div style={{ fontWeight: 500, marginBottom: "0.5rem" }}>Existing documents:</div>
                  {companyDocuments[editingId].map((doc) => {
                    const isMarkedForDelete = documentsToDelete[editingId]?.has(doc.id) || false;
                    return (
                      <div
                        key={doc.id}
                        className={styles.fileItem}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "0.5rem",
                          opacity: isMarkedForDelete ? 0.5 : 1,
                          textDecoration: isMarkedForDelete ? "line-through" : "none",
                        }}
                      >
                        <span>📄 {doc.original_filename} ({(doc.file_size / 1024).toFixed(1)} KB)</span>
                        <button
                          type="button"
                          onClick={() => toggleDocumentDelete(editingId, doc.id)}
                          style={{
                            padding: "0.25rem 0.5rem",
                            border: "1px solid #dc3545",
                            backgroundColor: isMarkedForDelete ? "#dc3545" : "#fff",
                            color: isMarkedForDelete ? "#fff" : "#dc3545",
                            borderRadius: "4px",
                            cursor: "pointer",
                            fontSize: "0.75rem",
                          }}
                          title={isMarkedForDelete ? "Restore document" : "Delete document"}
                        >
                          {isMarkedForDelete ? "✓ Restore" : "🗑️ Delete"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              <input
                type="file"
                multiple
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(e) => {
                  const files = Array.from(e.target.files || []);
                  setFormDocuments(files);
                }}
                className={styles.formFile}
              />
              {formDocuments.length > 0 && (
                <div className={styles.fileList} style={{ marginTop: "0.5rem" }}>
                  <div style={{ fontWeight: 500, marginBottom: "0.25rem" }}>New files to upload:</div>
                  {formDocuments.map((file, idx) => (
                    <div key={idx} className={styles.fileItem}>
                      📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)
                    </div>
                  ))}
                </div>
              )}
              <div className={styles.dialogActions}>
                <button
                  type="button"
                  data-testid="company-dialog-cancel"
                  onClick={() => {
                    setShowDialog(false);
                    setEditingId(null);
                    setFormName("");
                    setFormWebsite("");
                    setFormAudio(null);
                    setAudioToRemove(false);
                  }}
                  className={styles.cancelButton}
                  disabled={isCreating || isUpdating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="company-dialog-submit"
                  className={styles.submitButton}
                  disabled={isCreating || isUpdating}
                >
                  {isCreating
                    ? "Creating..."
                    : isUpdating
                    ? isUploadingDocuments
                      ? "Updating & Uploading..."
                      : "Updating..."
                    : editingId
                    ? "Update"
                    : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deletingId && (
        <div
          className={styles.dialogOverlay}
          data-testid="company-delete-dialog-overlay"
          onClick={() => setDeletingId(null)}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
            data-testid="company-delete-dialog"
          >
            <h3 className={styles.dialogTitle}>Delete Company</h3>
            <p>Are you sure you want to delete this company? This action cannot be undone.</p>
            <div className={styles.dialogActions}>
              <button
                type="button"
                data-testid="company-delete-cancel"
                onClick={() => setDeletingId(null)}
                className={styles.cancelButton}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="company-delete-confirm"
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
