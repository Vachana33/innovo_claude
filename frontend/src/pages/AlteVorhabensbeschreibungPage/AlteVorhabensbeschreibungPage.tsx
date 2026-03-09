import { useState, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { apiGet, apiDelete, apiUploadFiles, apiUploadFilePut, apiPost } from "../../utils/api";
import styles from "./AlteVorhabensbeschreibungPage.module.css";

type Document = {
  id: string;
  file_id: string;
  original_filename: string;
  uploaded_at: string;
  file_type: string;
  file_size: number;
};
type StyleSummary = {
    structure_patterns?: string[];
    tone_characteristics?: string[];
    writing_style_rules?: string[];
    storytelling_flow?: string[];
    common_section_headings?: string[];
  };
  

type StyleProfile = {
  status: "active" | "outdated" | "not_generated";
  documents_count: number;  // User's own documents
  total_documents_count?: number;  // Total system documents
  combined_hash: string | null;
  style_summary_json: StyleSummary | null;
  created_at: string | null;
  updated_at: string | null;
  profile_hash: string | null;
};

export default function AlteVorhabensbeschreibungPage() {
  const { logout } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState<Record<string, boolean>>({});
  const [isUpdating, setIsUpdating] = useState<Record<string, boolean>>({});
  const [styleProfile, setStyleProfile] = useState<StyleProfile | null>(null);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [formFiles, setFormFiles] = useState<File[]>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);


  // Fetch documents and style profile
  useEffect(() => {
    async function fetchData() {
      try {
        setIsLoading(true);
        const [docsData, profileData] = await Promise.all([
          apiGet<Document[]>("/alte-vorhabensbeschreibung/documents"),
          apiGet<StyleProfile>("/alte-vorhabensbeschreibung/style-profile"),
        ]);
        setDocuments(docsData);
        setStyleProfile(profileData);
      } catch (error: unknown) {
        console.error("Error fetching data:", error);
        if (error instanceof Error && error.message.includes("Authentication required")) {
          logout();
        }
      } finally {
        setIsLoading(false);
      }
    }
    fetchData();
  }, [logout]);

  // Handle file selection
  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    // Filter to only PDFs
    const pdfFiles = files.filter(
      (file) =>
        file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
    );
    setFormFiles(pdfFiles);
  }

  // Upload documents
  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (formFiles.length === 0) return;

    setIsUploading(true);
    try {
      const result = await apiUploadFiles("/alte-vorhabensbeschreibung/upload", formFiles);
      console.log("Upload result:", result);
      
      // Refresh data
      const [docsData, profileData] = await Promise.all([
        apiGet<Document[]>("/alte-vorhabensbeschreibung/documents"),
        apiGet<StyleProfile>("/alte-vorhabensbeschreibung/style-profile"),
      ]);
      setDocuments(docsData);
      setStyleProfile(profileData);
      
      setFormFiles([]);
      setShowUploadDialog(false);
      alert("Documents uploaded successfully!");
    } catch (error: unknown) {
      console.error("Error uploading documents:", error);
      alert(error instanceof Error ? error.message : "Failed to upload documents");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsUploading(false);
    }
  }

  // Update document
  async function handleUpdate(documentId: string) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,application/pdf";
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      if (!file.type.includes("pdf") && !file.name.toLowerCase().endsWith(".pdf")) {
        alert("Please select a PDF file");
        return;
      }

      setIsUpdating((prev) => ({ ...prev, [documentId]: true }));
      try {
        await apiUploadFilePut(`/alte-vorhabensbeschreibung/documents/${documentId}`, file);
        
        // Refresh data
        const [docsData, profileData] = await Promise.all([
          apiGet<Document[]>("/alte-vorhabensbeschreibung/documents"),
          apiGet<StyleProfile>("/alte-vorhabensbeschreibung/style-profile"),
        ]);
        setDocuments(docsData);
        setStyleProfile(profileData);
        
        alert("Document updated successfully!");
      } catch (error: unknown) {
        console.error("Error updating document:", error);
        alert(error instanceof Error ? error.message : "Failed to update document");
        if (error instanceof Error && error.message.includes("Authentication required")) {
          logout();
        }
      } finally {
        setIsUpdating((prev) => ({ ...prev, [documentId]: false }));
      }
    };
    input.click();
  }

  // Delete document
  async function handleDelete(documentId: string) {
    if (!confirm("Are you sure you want to delete this document?")) return;

    setIsDeleting((prev) => ({ ...prev, [documentId]: true }));
    try {
      await apiDelete(`/alte-vorhabensbeschreibung/documents/${documentId}`);
      
      // Refresh data
      const [docsData, profileData] = await Promise.all([
        apiGet<Document[]>("/alte-vorhabensbeschreibung/documents"),
        apiGet<StyleProfile>("/alte-vorhabensbeschreibung/style-profile"),
      ]);
      setDocuments(docsData);
      setStyleProfile(profileData);
      
      alert("Document deleted successfully!");
    } catch (error: unknown) {
      console.error("Error deleting document:", error);
      alert(error instanceof Error ? error.message : "Failed to delete document");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsDeleting((prev) => ({ ...prev, [documentId]: false }));
    }
  }

  // Regenerate style profile
  async function handleRegenerate() {
    if (!confirm("Regenerate style profile? This will analyze all uploaded documents.")) return;

    setIsRegenerating(true);
    try {
      await apiPost("/alte-vorhabensbeschreibung/regenerate-style", {});
      
      // Refresh style profile
      const profileData = await apiGet<StyleProfile>("/alte-vorhabensbeschreibung/style-profile");
      setStyleProfile(profileData);
      
      alert("Style profile regenerated successfully!");
    } catch (error: unknown) {
      console.error("Error regenerating style profile:", error);
      alert(error instanceof Error ? error.message : "Failed to regenerate style profile");
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsRegenerating(false);
    }
  }

  // Format date
  function formatDate(dateString: string) {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  // Format hash for display
  function formatHash(hash: string | null) {
    if (!hash) return "N/A";
    return `${hash.substring(0, 8)}...${hash.substring(hash.length - 8)}`;
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Alte Vorhabensbeschreibung</h1>
          <p className={styles.subtitle}>
            Historical writing style extraction for document generation
          </p>
        </div>
      </header>

      {/* Style Profile Status */}
      <div className={styles.styleProfileSection}>
        <h2 className={styles.sectionTitle}>Style Profile Status</h2>
        {isLoading ? (
          <div className={styles.loading}>Loading...</div>
        ) : styleProfile ? (
          <div className={styles.profileCard}>
            <div className={styles.profileRow}>
              <span className={styles.profileLabel}>Status:</span>
              <span
                className={`${styles.profileValue} ${
                  styleProfile.status === "active"
                    ? styles.statusActive
                    : styleProfile.status === "outdated"
                    ? styles.statusOutdated
                    : styles.statusNotGenerated
                }`}
              >
                {styleProfile.status === "active"
                  ? "Active"
                  : styleProfile.status === "outdated"
                  ? "Outdated"
                  : "Not Generated"}
              </span>
            </div>
            <div className={styles.profileRow}>
              <span className={styles.profileLabel}>Your Documents:</span>
              <span className={styles.profileValue}>{styleProfile.documents_count}</span>
            </div>
            {styleProfile.total_documents_count !== undefined && (
              <div className={styles.profileRow}>
                <span className={styles.profileLabel}>Total System Documents:</span>
                <span className={styles.profileValue}>{styleProfile.total_documents_count}</span>
              </div>
            )}
            <div className={styles.profileRow}>
              <span className={styles.profileLabel}>Current Hash:</span>
              <span className={styles.profileValueHash}>
                {formatHash(styleProfile.combined_hash)}
              </span>
            </div>
            {styleProfile.profile_hash && (
              <div className={styles.profileRow}>
                <span className={styles.profileLabel}>Profile Hash:</span>
                <span className={styles.profileValueHash}>
                  {formatHash(styleProfile.profile_hash)}
                </span>
              </div>
            )}
            {styleProfile.updated_at && (
              <div className={styles.profileRow}>
                <span className={styles.profileLabel}>Last Generated:</span>
                <span className={styles.profileValue}>
                  {formatDate(styleProfile.updated_at)}
                </span>
              </div>
            )}
            <button
              onClick={handleRegenerate}
              disabled={isRegenerating || styleProfile.documents_count === 0}
              className={styles.regenerateButton}
            >
              {isRegenerating ? "Regenerating..." : "Regenerate Style Profile"}
            </button>
          </div>
        ) : (
          <div className={styles.empty}>No style profile data available</div>
        )}
      </div>

      {/* Upload Section */}
      <div className={styles.uploadSection}>
        <h2 className={styles.sectionTitle}>Upload Documents</h2>
        <div className={styles.uploadArea}>
          <p className={styles.uploadDescription}>
            Upload PDF documents to extract writing style patterns. You can upload multiple files at once.
          </p>
          <button
            onClick={() => setShowUploadDialog(true)}
            className={styles.uploadButtonLarge}
            disabled={isUploading}
          >
            {isUploading ? "Uploading..." : "📄 Upload PDF Documents"}
          </button>
        </div>
      </div>

      {/* Documents List */}
      <div className={styles.documentsSection}>
        <h2 className={styles.sectionTitle}>Uploaded Documents ({documents.length})</h2>
        {isLoading ? (
          <div className={styles.loading}>Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className={styles.empty}>
            No documents uploaded yet. Use the upload button above to add PDF documents.
          </div>
        ) : (
          <div className={styles.documentsList}>
            {documents.map((doc) => (
              <div key={doc.id} className={styles.documentCard}>
                <div className={styles.documentInfo}>
                  <div className={styles.documentName}>📄 {doc.original_filename}</div>
                  <div className={styles.documentMeta}>
                    {(doc.file_size / 1024).toFixed(1)} KB •{" "}
                    {formatDate(doc.uploaded_at)}
                  </div>
                </div>
                <div className={styles.documentActions}>
                  <button
                    onClick={() => handleUpdate(doc.id)}
                    disabled={isUpdating[doc.id] || isDeleting[doc.id]}
                    className={styles.updateButton}
                    title="Update/Replace"
                  >
                    {isUpdating[doc.id] ? "Updating..." : "✏️ Update"}
                  </button>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    disabled={isDeleting[doc.id] || isUpdating[doc.id]}
                    className={styles.deleteButton}
                    title="Delete"
                  >
                    {isDeleting[doc.id] ? "Deleting..." : "🗑️ Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload Dialog */}
      {showUploadDialog && (
        <div
          className={styles.dialogOverlay}
          onClick={() => {
            setShowUploadDialog(false);
            setFormFiles([]);
          }}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className={styles.dialogTitle}>Upload PDF Documents</h3>
            <form onSubmit={handleUpload} className={styles.dialogForm}>
              <div className={styles.dialogFormContent}>
                <label className={styles.formLabel}>
                  PDF Files <span className={styles.required}>*</span>
                </label>
                <input
                  type="file"
                  multiple
                  accept=".pdf,application/pdf"
                  onChange={handleFileChange}
                  className={styles.formInput}
                />
                {formFiles.length > 0 && (
                  <div className={styles.fileList}>
                    <div style={{ marginBottom: "0.5rem", fontWeight: 500, fontSize: "0.95rem" }}>
                      Selected files ({formFiles.length}):
                    </div>
                    {formFiles.map((file, idx) => (
                      <div key={idx} className={styles.fileItem}>
                        📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className={styles.dialogActions}>
                <button
                  type="button"
                  onClick={() => {
                    setShowUploadDialog(false);
                    setFormFiles([]);
                  }}
                  className={styles.cancelButton}
                  disabled={isUploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.submitButton}
                  disabled={isUploading || formFiles.length === 0}
                >
                  {isUploading 
                    ? "Uploading..." 
                    : formFiles.length > 0 
                      ? `✓ Upload ${formFiles.length} File${formFiles.length > 1 ? 's' : ''}` 
                      : "Upload (Select Files)"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
