import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { apiGet, apiRequest, apiDownloadFile } from "../../utils/api";
import styles from "./ProjectWorkspacePage.module.css";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DocumentSection {
  id: string;
  title: string;
  type?: string;
  content?: string;
}

interface ProjectDocument {
  document_id: number;
  sections: DocumentSection[];
  has_content: boolean;
}

interface BatchProgress {
  status: "running" | "done" | "failed";
  sections?: string[];
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface StageProgress {
  status: "pending" | "running" | "done" | "failed";
  detail?: string;
}

interface ProjectContext {
  id: string;
  project_id: string;
  context_hash: string | null;
  completeness_score: number | null;
  company_discovery_status: string | null;
  assembly_progress_json: Record<string, StageProgress> | null;
  created_at: string;
  updated_at: string;
}

interface Project {
  id: string;
  company_id: number | null;
  company_name: string | null;
  funding_program_id: number | null;
  funding_program_title: string | null;
  topic: string;
  status: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  context: ProjectContext | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STAGE_KEYS: Array<{ key: string; label: string }> = [
  { key: "company",         label: "Company research"    },
  { key: "funding_rules",   label: "Funding rules"       },
  { key: "domain_research", label: "Domain research"     },
  { key: "examples",        label: "Historical examples" },
  { key: "style",           label: "Style profile"       },
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function ProjectWorkspacePage() {
  const { id } = useParams<{ id: string }>();

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fallback card state
  const [fallbackWebsite, setFallbackWebsite] = useState("");
  const [fallbackDescription, setFallbackDescription] = useState("");
  const [fallbackSubmitting, setFallbackSubmitting] = useState(false);
  const [fallbackError, setFallbackError] = useState<string | null>(null);
  const [fallbackSuccess, setFallbackSuccess] = useState(false);

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Preview mode (frontend-only — not persisted to backend)
  const [localPreviewMode, setLocalPreviewMode] = useState(false);
  const [previewSections, setPreviewSections] = useState<DocumentSection[]>([]);

  // Project document (sections + content)
  const [projectDocument, setProjectDocument] = useState<ProjectDocument | null>(null);

  // Generation batch progress
  const [generationBatches, setGenerationBatches] = useState<Record<string, BatchProgress> | null>(null);
  const [startingGeneration, setStartingGeneration] = useState(false);

  // Complete state: expanded sections accordion
  const [expandedSectionIds, setExpandedSectionIds] = useState<string[]>([]);

  // Download state
  const [downloading, setDownloading] = useState(false);

  // ── Data fetching ──────────────────────────────────────────────────────────

  useEffect(() => {
    if (!id) return;
    fetchProject();
  }, [id]);

  useEffect(() => {
    if (project?.status !== "assembling") return;
    const timer = setTimeout(fetchProject, 3000);
    return () => clearTimeout(timer);
  }, [project]);

  useEffect(() => {
    if (!id) return;
    fetchChatHistory();
  }, [id]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  useEffect(() => {
    if (!id || !project) return;
    if (project.status === "ready" || project.status === "complete") {
      fetchProjectDocument();
    }
  }, [project?.status]);

  useEffect(() => {
    if (project?.status !== "generating") return;
    const timer = setTimeout(fetchProject, 2000);
    return () => clearTimeout(timer);
  }, [project, generationBatches]);

  useEffect(() => {
    if (!project?.context?.assembly_progress_json) return;
    const batches = (project.context.assembly_progress_json as Record<string, unknown>)["generation_batches"];
    if (batches && typeof batches === "object") {
      setGenerationBatches(batches as Record<string, BatchProgress>);
    }
  }, [project?.context?.assembly_progress_json]);

  async function fetchProject() {
    try {
      const data = await apiGet<Project>(`/projects/${id}`);
      setProject(data);
    } catch {
      setError("Failed to load project.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchChatHistory() {
    try {
      const data = await apiGet<{ messages: ChatMessage[] }>(`/projects/${id}/chat`);
      setChatMessages(data.messages ?? []);
    } catch {
      setChatMessages([]);
    }
  }

  async function fetchProjectDocument() {
    try {
      const doc = await apiGet<ProjectDocument>(`/projects/${id}/document`);
      setProjectDocument(doc);
      if (!localPreviewMode) {
        setPreviewSections(doc.sections);
      }
      // Auto-expand first section in complete state
      if (doc.sections.length > 0 && expandedSectionIds.length === 0) {
        setExpandedSectionIds([doc.sections[0].id]);
      }
    } catch {
      // Document may not exist yet
    }
  }

  // ── Handlers ───────────────────────────────────────────────────────────────

  function handleEnterPreview() {
    if (projectDocument) setPreviewSections(projectDocument.sections);
    setLocalPreviewMode(true);
  }

  function handleDeletePreviewSection(sectionId: string) {
    setPreviewSections((prev) => prev.filter((s) => s.id !== sectionId));
  }

  async function handleGenerate() {
    if (!id || startingGeneration) return;
    setStartingGeneration(true);
    try {
      await apiRequest(`/projects/${id}/sections`, {
        method: "PATCH",
        body: JSON.stringify({ sections: previewSections }),
      });
      await apiRequest(`/projects/${id}/generate`, { method: "POST", body: "{}" });
      setLocalPreviewMode(false);
      setGenerationBatches(null);
      fetchProject();
    } catch {
      // Leave preview mode so user can retry
    } finally {
      setStartingGeneration(false);
    }
  }

  function toggleSection(sectionId: string) {
    setExpandedSectionIds((prev) =>
      prev.includes(sectionId) ? prev.filter((x) => x !== sectionId) : [...prev, sectionId]
    );
  }

  async function handleDownload(format: "pdf" | "docx") {
    if (!projectDocument?.document_id || downloading) return;
    setDownloading(true);
    try {
      const response = await apiDownloadFile(
        `/documents/${projectDocument.document_id}/export?format=${format}`,
      );
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `document.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Silent
    } finally {
      setDownloading(false);
    }
  }

  async function handleFallbackSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fallbackWebsite.trim() && !fallbackDescription.trim()) {
      setFallbackError("Please provide at least a website URL or a description.");
      return;
    }
    setFallbackSubmitting(true);
    setFallbackError(null);
    try {
      await apiRequest(`/projects/${id}/context`, {
        method: "PATCH",
        body: JSON.stringify({
          company_website: fallbackWebsite.trim() || null,
          company_description: fallbackDescription.trim() || null,
        }),
      });
      setFallbackSuccess(true);
      await fetchProject();
    } catch (err) {
      setFallbackError(err instanceof Error ? err.message : "Failed to submit company information.");
    } finally {
      setFallbackSubmitting(false);
    }
  }

  async function handleSendChat(e: React.FormEvent) {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text || chatSending) return;

    const optimisticUser: ChatMessage = {
      id: `optimistic-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, optimisticUser]);
    setChatInput("");
    setChatSending(true);

    try {
      const reply = await apiRequest<ChatMessage>(`/projects/${id}/chat`, {
        method: "POST",
        body: JSON.stringify({ message: text }),
      });
      setChatMessages((prev) => [...prev, reply]);
      await fetchProject();
    } catch {
      setChatMessages((prev) => prev.filter((m) => m.id !== optimisticUser.id));
    } finally {
      setChatSending(false);
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function getSectionGenStatus(sectionId: string): "done" | "running" | "pending" {
    if (!generationBatches) return "pending";
    for (const batch of Object.values(generationBatches)) {
      if (batch.sections?.includes(sectionId)) {
        if (batch.status === "done") return "done";
        if (batch.status === "running") return "running";
      }
    }
    return "pending";
  }

  function getDoneCount(): number {
    if (!generationBatches || !previewSections.length) return 0;
    return previewSections.filter((s) => getSectionGenStatus(s.id) === "done").length;
  }

  // ── Early returns ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className={styles.page}>
        <p className={styles.message}>Loading project...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className={styles.page}>
        <p className={styles.errorMessage}>{error ?? "Project not found."}</p>
      </div>
    );
  }

  const ctx = project.context;
  const isAssembling = project.status === "assembling";
  const isReady = project.status === "ready";
  const isGenerating = project.status === "generating";
  const isComplete = project.status === "complete";
  const showFallback = isReady && ctx?.company_discovery_status === "not_found" && !fallbackSuccess;

  const displaySections = localPreviewMode ? previewSections : (projectDocument?.sections ?? []);
  const totalSections = displaySections.length;
  const doneCount = getDoneCount();

  // ── Complete state — full-viewport layout ──────────────────────────────────

  if (isComplete && projectDocument) {
    return (
      <div className={styles.completePage}>
        {/* Top bar */}
        <div className={styles.completeTopBar}>
          <div className={styles.completeTopLeft}>
            <h1 className={styles.completeTitle}>{project.company_name ?? project.topic}</h1>
            <p className={styles.completeSubtitle}>
              {[project.funding_program_title, project.topic].filter(Boolean).join(" · ")}
            </p>
          </div>
          <div className={styles.completeTopActions}>
            <button
              className={styles.exportBtn}
              onClick={() => handleDownload("docx")}
              disabled={downloading}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              Export
            </button>
            <button
              className={styles.finalizeBtn}
              onClick={() => handleDownload("pdf")}
              disabled={downloading}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              Finalize
            </button>
          </div>
        </div>

        {/* Body: document + AI panel */}
        <div className={styles.completeBody}>
          {/* Document area */}
          <div className={styles.docArea}>
            {projectDocument.sections.map((section) => {
              const hasContent = (section.content ?? "").trim().length > 0;
              const isExpanded = expandedSectionIds.includes(section.id);
              return (
                <div key={section.id} className={styles.sectionAccordion}>
                  <button
                    className={styles.sectionAccordionHeader}
                    onClick={() => toggleSection(section.id)}
                  >
                    <span className={`${styles.sectionDot} ${hasContent ? styles.sectionDotFilled : styles.sectionDotEmpty}`} />
                    <span className={styles.sectionAccordionTitle}>{section.title}</span>
                    <span className={`${styles.sectionBadge} ${hasContent ? styles.sectionBadgeGenerated : styles.sectionBadgeDraft}`}>
                      {hasContent ? "Generated" : "Draft"}
                    </span>
                    <svg
                      className={`${styles.chevron} ${isExpanded ? styles.chevronOpen : ""}`}
                      width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    >
                      <polyline points="6 9 12 15 18 9"/>
                    </svg>
                  </button>

                  {isExpanded && (
                    <div className={styles.sectionBody}>
                      {hasContent ? (
                        <div className={styles.sectionTextContent}>
                          {section.content}
                        </div>
                      ) : (
                        <button
                          className={styles.askAiPrompt}
                          onClick={() => setChatInput(`Please generate content for the "${section.title}" section.`)}
                        >
                          Ask the AI assistant to generate content for this section →
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* AI Assistant panel */}
          <div className={styles.aiPanel}>
            <div className={styles.aiPanelHeader}>
              <div className={styles.aiPanelHeaderIcon}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
                </svg>
              </div>
              <div>
                <div className={styles.aiPanelTitle}>AI Assistant</div>
                <div className={styles.aiPanelSubtitle}>Innovo Agent</div>
              </div>
            </div>

            <div className={styles.aiChatArea}>
              {chatMessages.length === 0 ? (
                <div className={styles.aiIntro}>
                  <div className={styles.aiIntroIcon}>
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/>
                    </svg>
                  </div>
                  <p className={styles.aiIntroHeading}>How can I help?</p>
                  <p className={styles.aiIntroText}>
                    Ask me to update, rephrase, or generate content for any section.
                  </p>
                </div>
              ) : (
                <div className={styles.chatMessages}>
                  {chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={msg.role === "user" ? styles.chatBubbleUser : styles.chatBubbleAssistant}
                    >
                      {msg.content}
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>
              )}
            </div>

            <form onSubmit={handleSendChat} className={styles.aiInputArea}>
              <input
                type="text"
                className={styles.aiInput}
                placeholder="Ask the AI to update any section..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={chatSending}
              />
              <button
                type="submit"
                className={styles.aiSendBtn}
                disabled={chatSending || !chatInput.trim()}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // ── Assembling / Ready / Generating — centered card layout ─────────────────

  return (
    <div className={styles.page}>
      {/* ── Assembling state ── */}
      {isAssembling && (
        <div className={styles.centeredCard}>
          <div className={styles.assemblingIcon}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </div>
          <h2 className={styles.centeredTitle}>Assembling Context</h2>
          <p className={styles.centeredSubtitle}>Researching company and funding program…</p>
          <div className={styles.stageList}>
            {STAGE_KEYS.map(({ key, label }) => {
              const stage: StageProgress = ctx?.assembly_progress_json?.[key] ?? { status: "pending" };
              return (
                <div key={key} className={`${styles.stageRow} ${styles[`stageRow_${stage.status}`]}`}>
                  <span className={styles.stageIcon}>
                    {stage.status === "done" && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    )}
                    {stage.status === "running" && (
                      <svg className={styles.spinIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                    )}
                    {(stage.status === "pending" || stage.status === "failed") && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    )}
                  </span>
                  <span className={styles.stageLabel}>{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Ready state ── */}
      {isReady && (
        <div className={styles.workspaceCard}>
          {/* Project heading */}
          <div className={styles.projectHeading}>
            <h1 className={styles.projectTitle}>{project.company_name ?? project.topic}</h1>
            <p className={styles.projectSubtitle}>{project.topic}</p>
          </div>

          {/* Metadata grid */}
          <div className={styles.metaGrid}>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>COMPANY</span>
              <span className={styles.metaValue}>{project.company_name ?? "—"}</span>
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>FUNDING PROGRAM</span>
              <span className={styles.metaValue}>{project.funding_program_title ?? "—"}</span>
            </div>
            <div className={`${styles.metaItem} ${styles.metaItemFull}`}>
              <span className={styles.metaLabel}>TOPIC</span>
              <span className={styles.metaValue}>{project.topic}</span>
            </div>
          </div>

          {/* Fallback card */}
          {showFallback && (
            <div className={styles.fallbackCard}>
              <p className={styles.fallbackTitle}>Company information not found</p>
              <p className={styles.fallbackHint}>
                Provide a website or description to improve the generated document.
              </p>
              <form onSubmit={handleFallbackSubmit} className={styles.fallbackForm}>
                <input
                  type="text"
                  className={styles.fallbackInput}
                  placeholder="Company website (https://...)"
                  value={fallbackWebsite}
                  onChange={(e) => setFallbackWebsite(e.target.value)}
                />
                <textarea
                  className={styles.fallbackTextarea}
                  placeholder="Short description of what the company does..."
                  value={fallbackDescription}
                  onChange={(e) => setFallbackDescription(e.target.value)}
                  rows={3}
                />
                {fallbackError && <p className={styles.fallbackError}>{fallbackError}</p>}
                <button type="submit" className={styles.fallbackButton} disabled={fallbackSubmitting}>
                  {fallbackSubmitting ? "Submitting…" : "Submit"}
                </button>
              </form>
            </div>
          )}

          {/* Document structure */}
          <div className={styles.docStructure}>
            <div className={styles.docStructureHeader}>
              <span className={styles.docStructureTitle}>
                Document Structure
                {localPreviewMode && <span className={styles.previewBadge}>Preview Mode</span>}
              </span>
              <span className={styles.docStructureCount}>{totalSections} sections</span>
            </div>

            {displaySections.map((s, i) => (
              <div key={s.id} className={styles.sectionRow}>
                <span className={styles.dragHandle}>⋮⋮</span>
                <span className={styles.sectionNum}>{i + 1}</span>
                <span className={styles.sectionRowTitle}>{s.title}</span>
                {localPreviewMode && (
                  <div className={styles.sectionRowActions}>
                    <button
                      className={styles.sectionDeleteBtn}
                      onClick={() => handleDeletePreviewSection(s.id)}
                      title="Remove section"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
                      </svg>
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Hint bar */}
          <div className={styles.hintBar}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <span>
              Review and organize your document structure above.
              {!localPreviewMode && " When ready, click "}
              {!localPreviewMode && <strong>Start Generation</strong>}
              {localPreviewMode && " Remove sections you don't need, then confirm."}
            </span>
          </div>

          {/* Action button */}
          {!localPreviewMode ? (
            <button className={styles.generateBtn} onClick={handleEnterPreview}>
              ✨ Start Generation
            </button>
          ) : (
            <div className={styles.previewActions}>
              <button
                className={styles.previewBackBtn}
                onClick={() => setLocalPreviewMode(false)}
                disabled={startingGeneration}
              >
                Back
              </button>
              <button
                className={styles.generateBtn}
                onClick={handleGenerate}
                disabled={startingGeneration || previewSections.length === 0}
              >
                {startingGeneration ? "Starting…" : "✨ Confirm & Generate"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Generating state ── */}
      {isGenerating && (
        <div className={styles.generatingCard}>
          <div className={styles.genIcon}>✨</div>
          <h2 className={styles.centeredTitle}>Generating Document</h2>
          <p className={styles.centeredSubtitle}>AI is writing each section…</p>

          <div className={styles.genProgress}>
            <div className={styles.genProgressInfo}>
              <span>{doneCount} / {totalSections} sections complete</span>
              <span>{totalSections > 0 ? Math.round((doneCount / totalSections) * 100) : 0}%</span>
            </div>
            <div className={styles.genProgressTrack}>
              <div
                className={styles.genProgressFill}
                style={{ width: `${totalSections > 0 ? (doneCount / totalSections) * 100 : 0}%` }}
              />
            </div>
          </div>

          <div className={styles.genSectionList}>
            {displaySections.map((s) => {
              const status = getSectionGenStatus(s.id);
              return (
                <div
                  key={s.id}
                  className={`${styles.genSectionRow} ${styles[`genSectionRow_${status}`]}`}
                >
                  <span className={styles.genSectionIcon}>
                    {status === "done" && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="20 6 9 17 4 12"/></svg>
                    )}
                    {status === "running" && (
                      <svg className={styles.spinIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                    )}
                    {status === "pending" && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    )}
                  </span>
                  <span className={styles.genSectionLabel}>{s.title}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
