import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { apiGet, apiDelete, apiUploadFile, apiPost } from "../../utils/api";
import styles from "./KnowledgeBaseAdminPage.module.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type KBDocument = {
  id: string;
  filename: string;
  category: string;
  program_tag: string | null;
  uploaded_by: string;
  created_at: string;
};

type FundingProgram = {
  id: number;
  title: string;
};

type FundingSource = {
  id: string;
  funding_program_id: number;
  url: string;
  label: string | null;
  status: string;
  last_scraped_at: string | null;
  error_message: string | null;
  created_at: string;
};

type UploadMessage = {
  type: "success" | "error";
  text: string;
};

const CATEGORIES = [
  { value: "example", label: "Vorhabensbeschreibung (Beispiel)" },
  { value: "guideline", label: "Förderrichtlinie (Guideline)" },
  { value: "domain", label: "Domain Knowledge" },
  { value: "other", label: "Other" },
] as const;

type Category = (typeof CATEGORIES)[number]["value"];

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function categoryLabel(value: string): string {
  return CATEGORIES.find((c) => c.value === value)?.label ?? value;
}

function sourceStatusClass(status: string): string {
  if (status === "done") return styles.statusDone;
  if (status === "scraping") return styles.statusScraping;
  if (status === "failed") return styles.statusFailed;
  return styles.statusPending;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function KnowledgeBaseAdminPage() {
  const { logout } = useAuth();

  const [activeTab, setActiveTab] = useState<"documents" | "sources">("documents");
  const [accessDenied, setAccessDenied] = useState(false);

  // --- Documents tab state ---
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [category, setCategory] = useState<Category>("other");
  const [programTag, setProgramTag] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [docMessage, setDocMessage] = useState<UploadMessage | null>(null);
  const [isDeleting, setIsDeleting] = useState<Record<string, boolean>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docMsgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- Sources tab state ---
  const [sources, setSources] = useState<FundingSource[]>([]);
  const [fundingPrograms, setFundingPrograms] = useState<FundingProgram[]>([]);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceLabel, setSourceLabel] = useState("");
  const [sourceProgramId, setSourceProgramId] = useState<number | "">("");
  const [isAddingSource, setIsAddingSource] = useState(false);
  const [sourceMessage, setSourceMessage] = useState<UploadMessage | null>(null);
  const [isDeletingSource, setIsDeletingSource] = useState<Record<string, boolean>>({});
  const [isRefreshing, setIsRefreshing] = useState<Record<string, boolean>>({});
  const sourceMsgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------

  const fetchDocuments = useCallback(async () => {
    try {
      const docs = await apiGet<KBDocument[]>("/knowledge-base/documents");
      setDocuments(docs ?? []);
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (error.message === "AUTH_EXPIRED") logout();
        else if (error.message === "Admin access required") setAccessDenied(true);
      }
    }
  }, [logout]);

  const fetchSources = useCallback(async () => {
    try {
      const data = await apiGet<FundingSource[]>("/knowledge-base/funding-sources");
      setSources(data ?? []);
    } catch (error: unknown) {
      if (error instanceof Error && error.message === "AUTH_EXPIRED") logout();
    }
  }, [logout]);

  const fetchFundingPrograms = useCallback(async () => {
    try {
      const data = await apiGet<FundingProgram[]>("/funding-programs");
      setFundingPrograms(data ?? []);
    } catch {
      // non-critical
    }
  }, []);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      await fetchDocuments();
      setIsLoading(false);
    }
    load();
  }, [fetchDocuments]);

  useEffect(() => {
    fetchSources();
    fetchFundingPrograms();
  }, [fetchSources, fetchFundingPrograms]);

  // ---------------------------------------------------------------------------
  // Message helpers
  // ---------------------------------------------------------------------------

  function showDocMessage(type: UploadMessage["type"], text: string) {
    if (docMsgTimerRef.current) clearTimeout(docMsgTimerRef.current);
    setDocMessage({ type, text });
    docMsgTimerRef.current = setTimeout(() => setDocMessage(null), 5000);
  }

  function showSourceMessage(type: UploadMessage["type"], text: string) {
    if (sourceMsgTimerRef.current) clearTimeout(sourceMsgTimerRef.current);
    setSourceMessage({ type, text });
    sourceMsgTimerRef.current = setTimeout(() => setSourceMessage(null), 5000);
  }

  // ---------------------------------------------------------------------------
  // Document upload / delete
  // ---------------------------------------------------------------------------

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) return;
    if (!ACCEPTED_TYPES.includes(file.type) && !file.name.match(/\.(pdf|docx|doc)$/i)) {
      showDocMessage("error", "Only PDF and DOCX files are accepted.");
      e.target.value = "";
      return;
    }
    setSelectedFile(file);
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) return;

    let endpoint = `/knowledge-base/documents?category=${encodeURIComponent(category)}`;
    if (programTag.trim()) {
      endpoint += `&program_tag=${encodeURIComponent(programTag.trim())}`;
    }

    setIsUploading(true);
    try {
      await apiUploadFile(endpoint, selectedFile);
      showDocMessage("success", `"${selectedFile.name}" uploaded successfully.`);
      setSelectedFile(null);
      setProgramTag("");
      setCategory("other");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await fetchDocuments();
    } catch (error: unknown) {
      if (error instanceof Error && error.message === "AUTH_EXPIRED") logout();
      else showDocMessage("error", error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDeleteDoc(doc: KBDocument) {
    if (!confirm(`Delete "${doc.filename}"? This will also remove all its chunks and embeddings.`)) return;
    setIsDeleting((prev) => ({ ...prev, [doc.id]: true }));
    try {
      await apiDelete(`/knowledge-base/documents/${doc.id}`);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (error: unknown) {
      if (error instanceof Error && error.message === "AUTH_EXPIRED") logout();
      else showDocMessage("error", error instanceof Error ? error.message : "Delete failed.");
    } finally {
      setIsDeleting((prev) => ({ ...prev, [doc.id]: false }));
    }
  }

  // ---------------------------------------------------------------------------
  // Source add / delete / refresh
  // ---------------------------------------------------------------------------

  async function handleAddSource(e: React.FormEvent) {
    e.preventDefault();
    if (!sourceUrl.trim() || sourceProgramId === "") return;

    setIsAddingSource(true);
    try {
      await apiPost("/knowledge-base/funding-sources", {
        funding_program_id: sourceProgramId,
        url: sourceUrl.trim(),
        label: sourceLabel.trim() || null,
      });
      showSourceMessage("success", "Source added. Initial scrape queued in the background.");
      setSourceUrl("");
      setSourceLabel("");
      setSourceProgramId("");
      await fetchSources();
    } catch (error: unknown) {
      if (error instanceof Error && error.message === "AUTH_EXPIRED") logout();
      else showSourceMessage("error", error instanceof Error ? error.message : "Failed to add source.");
    } finally {
      setIsAddingSource(false);
    }
  }

  async function handleDeleteSource(source: FundingSource) {
    if (!confirm(`Delete source "${source.url}"? This will remove all scraped chunks.`)) return;
    setIsDeletingSource((prev) => ({ ...prev, [source.id]: true }));
    try {
      await apiDelete(`/knowledge-base/funding-sources/${source.id}`);
      setSources((prev) => prev.filter((s) => s.id !== source.id));
    } catch (error: unknown) {
      if (error instanceof Error && error.message === "AUTH_EXPIRED") logout();
      else showSourceMessage("error", error instanceof Error ? error.message : "Delete failed.");
    } finally {
      setIsDeletingSource((prev) => ({ ...prev, [source.id]: false }));
    }
  }

  async function handleRefreshSource(source: FundingSource) {
    setIsRefreshing((prev) => ({ ...prev, [source.id]: true }));
    try {
      await apiPost(`/knowledge-base/funding-sources/${source.id}/refresh`, {});
      showSourceMessage("success", `Re-scrape queued for "${source.url}".`);
      await fetchSources();
    } catch (error: unknown) {
      if (error instanceof Error && error.message === "AUTH_EXPIRED") logout();
      else showSourceMessage("error", error instanceof Error ? error.message : "Refresh failed.");
    } finally {
      setIsRefreshing((prev) => ({ ...prev, [source.id]: false }));
    }
  }

  // ---------------------------------------------------------------------------
  // Render guards
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div className={styles.container}>
        <p className={styles.loadingText}>Loading…</p>
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className={styles.container}>
        <div className={styles.accessDenied}>
          <h2 className={styles.accessDeniedTitle}>Access Denied</h2>
          <p className={styles.accessDeniedText}>
            This page requires admin access. Contact your administrator if you
            believe this is an error.
          </p>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------------------

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerIcon}>🛡️</div>
        <div className={styles.headerText}>
          <h1 className={styles.title}>Admin Dashboard</h1>
          <p className={styles.subtitle}>Manage knowledge base and funding program sources</p>
        </div>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === "documents" ? styles.tabActive : ""}`}
          onClick={() => setActiveTab("documents")}
        >
          Documents
          <span className={styles.tabBadge}>{documents.length}</span>
        </button>
        <button
          className={`${styles.tab} ${activeTab === "sources" ? styles.tabActive : ""}`}
          onClick={() => setActiveTab("sources")}
        >
          Funding Sources
          <span className={styles.tabBadge}>{sources.length}</span>
        </button>
      </div>

      {/* ===== DOCUMENTS TAB ===== */}
      {activeTab === "documents" && (
        <>
          {/* Upload section */}
          <section className={styles.uploadSection}>
            <h2 className={styles.sectionTitle}>Upload Document</h2>
            <form onSubmit={handleUpload} className={styles.uploadForm}>
              <div
                className={styles.uploadArea}
                onClick={() => fileInputRef.current?.click()}
              >
                <span className={styles.uploadIcon}>📄</span>
                {selectedFile ? (
                  <p className={styles.selectedFilename}>{selectedFile.name}</p>
                ) : (
                  <p className={styles.uploadDescription}>
                    Click to select a PDF or DOCX file
                  </p>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc"
                  onChange={handleFileChange}
                  className={styles.hiddenInput}
                />
              </div>

              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.label} htmlFor="category">
                    Category
                  </label>
                  <select
                    id="category"
                    className={styles.select}
                    value={category}
                    onChange={(e) => setCategory(e.target.value as Category)}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.label} htmlFor="programTag">
                    Program Tag{" "}
                    <span className={styles.optional}>(optional)</span>
                  </label>
                  <input
                    id="programTag"
                    type="text"
                    className={styles.input}
                    placeholder="e.g. ZIM, KMU-innovativ"
                    value={programTag}
                    onChange={(e) => setProgramTag(e.target.value)}
                  />
                </div>

                <div className={styles.formGroupSubmit}>
                  <button
                    type="submit"
                    className={styles.uploadButton}
                    disabled={!selectedFile || isUploading}
                  >
                    {isUploading ? "Uploading…" : "Upload"}
                  </button>
                </div>
              </div>

              {docMessage && (
                <div
                  className={
                    docMessage.type === "success"
                      ? styles.messageSuccess
                      : styles.messageError
                  }
                >
                  {docMessage.text}
                </div>
              )}
            </form>
          </section>

          {/* Documents list */}
          <section className={styles.documentsSection}>
            <h2 className={styles.sectionTitle}>
              Uploaded Documents{" "}
              <span className={styles.count}>{documents.length}</span>
            </h2>

            {documents.length === 0 ? (
              <p className={styles.emptyText}>
                No documents uploaded yet. Upload a PDF or DOCX above to get started.
              </p>
            ) : (
              <div className={styles.tableWrapper}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th className={styles.th}>Filename</th>
                      <th className={styles.th}>Category</th>
                      <th className={styles.th}>Program Tag</th>
                      <th className={styles.th}>Uploaded</th>
                      <th className={styles.th}>By</th>
                      <th className={styles.th}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc) => (
                      <tr key={doc.id} className={styles.tr}>
                        <td className={styles.td}>
                          <span className={styles.filename}>{doc.filename}</span>
                        </td>
                        <td className={styles.td}>
                          <span
                            className={`${styles.badge} ${
                              styles[`badge_${doc.category}`] ?? styles.badge_other
                            }`}
                          >
                            {categoryLabel(doc.category)}
                          </span>
                        </td>
                        <td className={styles.td}>
                          {doc.program_tag ? (
                            <span className={styles.tag}>{doc.program_tag}</span>
                          ) : (
                            <span className={styles.emptyCell}>—</span>
                          )}
                        </td>
                        <td className={styles.td}>{formatDate(doc.created_at)}</td>
                        <td className={styles.td}>
                          <span className={styles.email}>{doc.uploaded_by}</span>
                        </td>
                        <td className={styles.td}>
                          <button
                            className={styles.deleteButton}
                            onClick={() => handleDeleteDoc(doc)}
                            disabled={isDeleting[doc.id]}
                          >
                            {isDeleting[doc.id] ? "…" : "Delete"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {/* ===== FUNDING SOURCES TAB ===== */}
      {activeTab === "sources" && (
        <>
          {/* Add source form */}
          <section className={styles.uploadSection}>
            <h2 className={styles.sectionTitle}>Add Funding Source URL</h2>
            <p className={styles.sourcesHint}>
              Add a funding program website URL. It will be scraped automatically and
              indexed as guideline knowledge. The scraper runs every Monday at 02:00 and
              skips pages that haven't changed.
            </p>
            <form onSubmit={handleAddSource} className={styles.uploadForm}>
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.label} htmlFor="sourceProgramId">
                    Funding Program
                  </label>
                  <select
                    id="sourceProgramId"
                    className={styles.select}
                    value={sourceProgramId}
                    onChange={(e) =>
                      setSourceProgramId(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">— Select program —</option>
                    {fundingPrograms.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div className={styles.formGroup} style={{ flex: 2 }}>
                  <label className={styles.label} htmlFor="sourceUrl">
                    URL
                  </label>
                  <input
                    id="sourceUrl"
                    type="url"
                    className={styles.input}
                    placeholder="https://www.foerderdatenbank.de/..."
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.label} htmlFor="sourceLabel">
                    Label <span className={styles.optional}>(optional)</span>
                  </label>
                  <input
                    id="sourceLabel"
                    type="text"
                    className={styles.input}
                    placeholder="e.g. ZIM Richtlinie"
                    value={sourceLabel}
                    onChange={(e) => setSourceLabel(e.target.value)}
                  />
                </div>

                <div className={styles.formGroupSubmit}>
                  <button
                    type="submit"
                    className={styles.uploadButton}
                    disabled={!sourceUrl.trim() || sourceProgramId === "" || isAddingSource}
                  >
                    {isAddingSource ? "Adding…" : "Add"}
                  </button>
                </div>
              </div>

              {sourceMessage && (
                <div
                  className={
                    sourceMessage.type === "success"
                      ? styles.messageSuccess
                      : styles.messageError
                  }
                >
                  {sourceMessage.text}
                </div>
              )}
            </form>
          </section>

          {/* Sources list */}
          <section className={styles.documentsSection}>
            <h2 className={styles.sectionTitle}>
              Registered Sources{" "}
              <span className={styles.count}>{sources.length}</span>
            </h2>

            {sources.length === 0 ? (
              <p className={styles.emptyText}>
                No sources added yet. Add a URL above to get started.
              </p>
            ) : (
              <div className={styles.tableWrapper}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th className={styles.th}>URL / Label</th>
                      <th className={styles.th}>Program</th>
                      <th className={styles.th}>Status</th>
                      <th className={styles.th}>Last Scraped</th>
                      <th className={styles.th}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((src) => {
                      const prog = fundingPrograms.find(
                        (p) => p.id === src.funding_program_id
                      );
                      return (
                        <tr key={src.id} className={styles.tr}>
                          <td className={styles.td}>
                            <div className={styles.sourceUrlCell}>
                              <span className={styles.filename}>
                                {src.label || src.url}
                              </span>
                              {src.label && (
                                <span className={styles.sourceUrlSub}>{src.url}</span>
                              )}
                              {src.status === "failed" && src.error_message && (
                                <span className={styles.sourceError}>
                                  {src.error_message}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className={styles.td}>
                            {prog ? (
                              <span className={styles.tag}>{prog.title}</span>
                            ) : (
                              <span className={styles.emptyCell}>—</span>
                            )}
                          </td>
                          <td className={styles.td}>
                            <span className={`${styles.statusBadge} ${sourceStatusClass(src.status)}`}>
                              {src.status}
                            </span>
                          </td>
                          <td className={styles.td}>
                            {src.last_scraped_at
                              ? formatDate(src.last_scraped_at)
                              : <span className={styles.emptyCell}>Never</span>}
                          </td>
                          <td className={styles.td}>
                            <div className={styles.actionButtons}>
                              <button
                                className={styles.refreshButton}
                                onClick={() => handleRefreshSource(src)}
                                disabled={isRefreshing[src.id] || src.status === "scraping"}
                                title="Re-scrape now"
                              >
                                {isRefreshing[src.id] ? "…" : "Refresh"}
                              </button>
                              <button
                                className={styles.deleteButton}
                                onClick={() => handleDeleteSource(src)}
                                disabled={isDeletingSource[src.id]}
                              >
                                {isDeletingSource[src.id] ? "…" : "Delete"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
