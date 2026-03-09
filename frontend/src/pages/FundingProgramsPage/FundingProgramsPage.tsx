import { useState, useEffect } from "react";

import { useAuth } from "../../contexts/AuthContext";
import { apiGet, apiPost, apiPut, apiDelete, apiUploadFiles } from "../../utils/api";
import styles from "./FundingProgramsPage.module.css";

type FundingProgram = {
  id: number;
  title: string;
  website?: string;
  created_at: string;
};

export default function FundingProgramsPage() {

  const { logout } = useAuth();
  const [programs, setPrograms] = useState<FundingProgram[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);

  const [formTitle, setFormTitle] = useState("");
  const [formWebsite, setFormWebsite] = useState("");
  const [formFiles, setFormFiles] = useState<File[]>([]);
  const [existingDocuments, setExistingDocuments] = useState<Array<{id: string; original_filename: string; file_type: string; file_size: number}>>([]);
  const [documentsToDelete, setDocumentsToDelete] = useState<Set<string>>(new Set());

  // Fetch programs
  useEffect(() => {
    async function fetchPrograms() {
      try {
        setIsLoading(true);
        const data = await apiGet<FundingProgram[]>("/funding-programs");
        setPrograms(data);
      } catch (error: unknown) {
        console.error("Error fetching funding programs:", error);
        if (error instanceof Error && error.message.includes("Authentication required")) {
          logout();
        }
      } finally {
        setIsLoading(false);
      }
    }
    fetchPrograms();
  }, [logout]);

  // Filter programs
  const filteredPrograms = programs.filter((p) => {
    if (!searchTerm.trim()) return true;
    const searchLower = searchTerm.toLowerCase();
    return (
      p.title.toLowerCase().includes(searchLower) ||
      (p.website && p.website.toLowerCase().includes(searchLower))
    );
  });

  // Create program
  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formTitle.trim()) return;

    setIsCreating(true);
    try {
      const created = await apiPost<FundingProgram>("/funding-programs", {
        title: formTitle.trim(),
        website: formWebsite.trim() || undefined,
      });
      setPrograms((prev) => [created, ...prev]);
      
      // Upload files if any were selected
      if (formFiles.length > 0) {
        setIsUploading(true);
        try {
          // Filter to only PDF and DOCX files
          const validFiles = formFiles.filter(
            (file) => file.type === "application/pdf" || 
                     file.name.toLowerCase().endsWith(".pdf") ||
                     file.name.toLowerCase().endsWith(".docx") ||
                     file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          );
          
          if (validFiles.length > 0) {
            await apiUploadFiles(`/funding-programs/${created.id}/guidelines/upload`, validFiles);
          }
        } catch (uploadError: unknown) {
          console.error("Error uploading files:", uploadError);
          alert(uploadError instanceof Error ? uploadError.message : "Failed to upload files");
        } finally {
          setIsUploading(false);
        }
      }
      
      setFormTitle("");
      setFormWebsite("");
      setFormFiles([]);
      setShowDialog(false);
    } catch (error: unknown) {
      console.error("Error creating program:", error);
      alert(error instanceof Error ? error.message : "Failed to create program");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsCreating(false);
    }
  }

  // Update program
  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId || !formTitle.trim()) return;

    setIsUpdating(true);
    try {
      const updated = await apiPut<FundingProgram>(`/funding-programs/${editingId}`, {
        title: formTitle.trim(),
        website: formWebsite.trim() || undefined,
      });
      setPrograms((prev) => prev.map((p) => (p.id === editingId ? updated : p)));
      
      // Delete documents that were marked for deletion
      if (documentsToDelete.size > 0) {
        setIsUploading(true);
        try {
          for (const docId of documentsToDelete) {
            await apiDelete(`/funding-programs/${editingId}/documents/${docId}`);
          }
        } catch (deleteError: unknown) {
          console.error("Error deleting documents:", deleteError);
          alert(deleteError instanceof Error ? deleteError.message : "Failed to delete some documents");
        } finally {
          setIsUploading(false);
        }
      }
      
      // Upload new files if any were selected
      if (formFiles.length > 0) {
        setIsUploading(true);
        try {
          // Filter to only PDF and DOCX files
          const validFiles = formFiles.filter(
            (file) => file.type === "application/pdf" || 
                     file.name.toLowerCase().endsWith(".pdf") ||
                     file.name.toLowerCase().endsWith(".docx") ||
                     file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          );
          
          if (validFiles.length > 0) {
            await apiUploadFiles(`/funding-programs/${editingId}/guidelines/upload`, validFiles);
          }
        } catch (uploadError: unknown) {
          console.error("Error uploading files:", uploadError);
          alert(uploadError instanceof Error ? uploadError.message : "Failed to upload files");
        } finally {
          setIsUploading(false);
        }
      }
      
      setEditingId(null);
      setFormTitle("");
      setFormWebsite("");
      setFormFiles([]);
      setExistingDocuments([]);
      setDocumentsToDelete(new Set());
      setShowDialog(false);
    } catch (error: unknown) {
      console.error("Error updating program:", error);
      alert(error instanceof Error ? error.message : "Failed to update program");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsUpdating(false);
    }
  }

  // Delete program
  async function handleDelete() {
    if (!deletingId) return;

    setIsDeleting(true);
    try {
      await apiDelete(`/funding-programs/${deletingId}`);
      setPrograms((prev) => prev.filter((p) => p.id !== deletingId));
      setDeletingId(null);
    } catch (error: unknown) {
      console.error("Error deleting program:", error);
      alert(error instanceof Error ? error.message : "Failed to delete program");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsDeleting(false);
    }
  }

  // Open edit dialog
  async function openEditDialog(program: FundingProgram) {
    setEditingId(program.id);
    setFormTitle(program.title);
    setFormWebsite(program.website || "");
    setFormFiles([]);
    setExistingDocuments([]);
    setDocumentsToDelete(new Set());
    setOpenMenuId(null);
    setShowDialog(true);
    
    // Fetch existing guidelines documents
    try {
      const response = await apiGet<{documents: Array<{id: string; original_filename: string; file_type: string; file_size: number}>}>(
        `/funding-programs/${program.id}/documents?category=guidelines`
      );
      setExistingDocuments(response.documents || []);
    } catch (error: unknown) {
      console.error("Error fetching documents:", error);
      // Don't show error to user - just continue without documents
    }
  }

  // Toggle document deletion
  function toggleDocumentDelete(docId: string) {
    setDocumentsToDelete(prev => {
      const newSet = new Set(prev);
      if (newSet.has(docId)) {
        newSet.delete(docId);
      } else {
        newSet.add(docId);
      }
      return newSet;
    });
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
    <div className={styles.container} data-testid="page-funding-programs">
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Funding Programs</h1>
          <p className={styles.subtitle}>
            Manage grant opportunities and funding sources.
          </p>
        </div>
        <button
          data-testid="funding-new-program-btn"
          onClick={() => {
            setEditingId(null);
            setFormTitle("");
            setFormWebsite("");
            
            setFormFiles([]);
            setShowDialog(true);
          }}
          className={styles.newButton}
        >
          + New Program
        </button>
      </header>

      <div className={styles.searchBar}>
        <input
          data-testid="funding-search"
          type="text"
          placeholder="Search programs..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className={styles.searchInput}
        />
      </div>

      <div className={styles.programsGrid} data-testid="funding-programs-list">
        {isLoading ? (
          <div className={styles.loading} data-testid="funding-loading">Loading programs...</div>
        ) : filteredPrograms.length === 0 ? (
          <div className={styles.empty} data-testid="funding-empty">
            {programs.length === 0
              ? "No funding programs found. Create your first program!"
              : `No programs match "${searchTerm}"`}
          </div>
        ) : (
          filteredPrograms.map((program) => (
            <div key={program.id} className={styles.programCard} data-testid="funding-program-card">
              <div className={styles.cardHeader}>
                <h3 className={styles.cardTitle}>{program.title}</h3>
                <p>{formatDate(program.created_at)}</p>

                <div className={styles.cardActions}>
                  <button
                    data-testid={`funding-program-menu-${program.id}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenuId(openMenuId === program.id ? null : program.id);
                    }}
                    className={styles.menuButton}
                    title="More options"
                  >
                    ⋮
                  </button>
                  {openMenuId === program.id && (
                    <div className={styles.menuDropdown} data-testid={`funding-program-menu-dropdown-${program.id}`}>
                      <button
                        data-testid={`funding-program-edit-${program.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          openEditDialog(program);
                        }}
                        className={styles.menuItem}
                      >
                        Edit
                  </button>
                  <button
                        data-testid={`funding-program-delete-${program.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingId(program.id);
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
              {program.website && (
                <a
                  href={program.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.visitButton}
                >
                  <span className={styles.visitIcon}>🌐</span>
                  Visit Website
                </a>
              )}
            </div>
          ))
        )}
      </div>

      {/* Create/Edit Dialog */}
      {showDialog && (
        <div
          className={styles.dialogOverlay}
          data-testid="funding-dialog-overlay"
          onClick={() => {
            setShowDialog(false);
            setEditingId(null);
            setFormTitle("");
            setFormWebsite("");
            setFormFiles([]);
          }}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
            data-testid="funding-dialog"
          >
            <h3 className={styles.dialogTitle}>
              {editingId ? "Edit Funding Program" : "New Funding Program"}
            </h3>
            <form onSubmit={editingId ? handleUpdate : handleCreate} data-testid="funding-form">
              <label className={styles.formLabel}>
                Title <span className={styles.required}>*</span>
              </label>
              <input
                data-testid="funding-form-title"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                required
                className={styles.formInput}
                placeholder="e.g. Green Tech Innovation Grant"
              />
              <label className={styles.formLabel}>Website (optional)</label>
              <input
                data-testid="funding-form-website"
                value={formWebsite}
                onChange={(e) => setFormWebsite(e.target.value)}
                className={styles.formInput}
                placeholder="https://..."
              />
              <label className={styles.formLabel}>Guidelines Documents (optional)</label>
              {editingId && existingDocuments.length > 0 && (
                <div className={styles.fileList}>
                  <div style={{ marginBottom: "0.5rem", fontWeight: 500 }}>Existing documents:</div>
                  {existingDocuments.map((doc) => {
                    const isMarkedForDelete = documentsToDelete.has(doc.id);
                    return (
                      <div 
                        key={doc.id} 
                        className={styles.fileItem}
                        style={{
                          opacity: isMarkedForDelete ? 0.5 : 1,
                          textDecoration: isMarkedForDelete ? "line-through" : "none",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "0.5rem"
                        }}
                      >
                        <span>📄 {doc.original_filename} ({(doc.file_size / 1024).toFixed(1)} KB)</span>
                        <button
                          type="button"
                          onClick={() => toggleDocumentDelete(doc.id)}
                          style={{
                            padding: "0.25rem 0.5rem",
                            border: "1px solid #dc3545",
                            backgroundColor: isMarkedForDelete ? "#dc3545" : "#fff",
                            color: isMarkedForDelete ? "#fff" : "#dc3545",
                            borderRadius: "4px",
                            cursor: "pointer",
                            fontSize: "0.75rem"
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
                  setFormFiles(files);
                }}
                className={styles.formInput}
              />
              {formFiles.length > 0 && (
                <div className={styles.fileList}>
                  <div style={{ marginBottom: "0.5rem", fontWeight: 500 }}>New files to upload:</div>
                  {formFiles.map((file, idx) => (
                    <div key={idx} className={styles.fileItem}>
                      📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)
                    </div>
                  ))}
                </div>
              )}
              <div className={styles.dialogActions}>
                <button
                  type="button"
                  data-testid="funding-dialog-cancel"
                  onClick={() => {
                    setShowDialog(false);
                    setEditingId(null);
                    setFormTitle("");
                    setFormWebsite("");
                    setFormFiles([]);
                    setDocumentsToDelete(new Set());
                  }}
                  className={styles.cancelButton}
                  disabled={isCreating || isUpdating || isUploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="funding-dialog-submit"
                  className={styles.submitButton}
                  disabled={isCreating || isUpdating || isUploading}
                >
                  {isCreating
                    ? "Creating..."
                    : isUploading
                    ? "Uploading..."
                    : isUpdating
                    ? "Updating..."
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
          data-testid="funding-delete-dialog-overlay"
          onClick={() => setDeletingId(null)}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
            data-testid="funding-delete-dialog"
          >
            <h3 className={styles.dialogTitle}>Delete Funding Program</h3>
            <p>Are you sure you want to delete this funding program? This action cannot be undone.</p>
            <div className={styles.dialogActions}>
              <button
                type="button"
                data-testid="funding-delete-cancel"
                onClick={() => setDeletingId(null)}
                className={styles.cancelButton}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="funding-delete-confirm"
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
