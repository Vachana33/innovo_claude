import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiRequest } from "../../utils/api";
import styles from "./ProjectWorkspacePage.module.css";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DocumentSection {
  id: string;
  title: string;
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

const STATUS_LABELS: Record<string, string> = {
  assembling: "Assembling context...",
  ready: "Ready to generate",
  generating: "Generating document...",
  complete: "Document complete",
};

const STAGE_KEYS: Array<{ key: string; label: string }> = [
  { key: "company",         label: "Company research"   },
  { key: "funding_rules",   label: "Funding rules"      },
  { key: "domain_research", label: "Domain research"    },
  { key: "examples",        label: "Historical examples" },
  { key: "style",           label: "Style profile"      },
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function ProjectWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Section list state — populated when project is ready and company_id is resolved
  const [sections, setSections] = useState<DocumentSection[]>([]);

  // Fallback card state
  const [fallbackWebsite, setFallbackWebsite] = useState("");
  const [fallbackDescription, setFallbackDescription] = useState("");
  const [fallbackSubmitting, setFallbackSubmitting] = useState(false);
  const [fallbackError, setFallbackError] = useState<string | null>(null);
  const [fallbackSuccess, setFallbackSuccess] = useState(false);

  // ── Data fetching ──────────────────────────────────────────────────────────

  useEffect(() => {
    if (!id) return;
    fetchProject();
  }, [id]);

  // Poll every 3 seconds while assembling; stop and clean up once ready.
  useEffect(() => {
    if (project?.status !== "assembling") return;
    const timer = setTimeout(fetchProject, 3000);
    return () => clearTimeout(timer);
  }, [project]);

  // Fetch document sections once the project is ready and company_id is resolved.
  useEffect(() => {
    if (!project || project.status !== "ready" || !project.company_id) return;
    fetchSections(project.company_id);
  }, [project?.status, project?.company_id]);

  async function fetchSections(companyId: number) {
    try {
      const doc = await apiGet<{ content_json: { sections: DocumentSection[] } }>(
        `/documents/${companyId}/vorhabensbeschreibung`
      );
      setSections(doc.content_json?.sections ?? []);
    } catch {
      setSections([]);
    }
  }

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

  // ── Fallback submit ────────────────────────────────────────────────────────

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
        <button className={styles.backButton} onClick={() => navigate("/dashboard")}>
          ← Back to Projects
        </button>
      </div>
    );
  }

  const ctx = project.context;
  const isAssembling = project.status === "assembling";
  const isReady = project.status === "ready";
  const showFallback =
    isReady &&
    ctx?.company_discovery_status === "not_found" &&
    !fallbackSuccess;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <button className={styles.backButton} onClick={() => navigate("/dashboard")}>
          ← Projects
        </button>
      </div>

      <div className={styles.layout}>
        {/* ── Main content ── */}
        <div className={styles.main}>
          <h1 className={styles.topic}>{project.topic}</h1>

          <div className={styles.statusRow}>
            <span className={`${styles.statusBadge} ${styles[`status_${project.status}`]}`}>
              {project.status}
            </span>
            <span className={styles.statusLabel}>
              {STATUS_LABELS[project.status] ?? project.status}
            </span>
          </div>

          {/* Assembly progress panel — shown while assembling */}
          {isAssembling && (
            <div className={styles.progressPanel}>
              <p className={styles.progressTitle}>Assembling context…</p>
              <ul className={styles.stageList}>
                {STAGE_KEYS.map(({ key, label }) => {
                  const stage: StageProgress =
                    ctx?.assembly_progress_json?.[key] ?? { status: "pending" };
                  return (
                    <li key={key} className={styles.stageItem}>
                      <span
                        className={`${styles.stageDot} ${styles[`stageDot_${stage.status}`]}`}
                      />
                      <span className={styles.stageLabel}>{label}</span>
                      <span className={styles.stageStatus}>{stage.status}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Company fallback card — shown when discovery failed */}
          {showFallback && (
            <div className={styles.fallbackCard}>
              <p className={styles.fallbackTitle}>Company information not found</p>
              <p className={styles.fallbackHint}>
                The system could not find information about this company automatically.
                Provide a website or a short description to improve the generated document.
              </p>
              <form onSubmit={handleFallbackSubmit} className={styles.fallbackForm}>
                <label className={styles.fallbackLabel}>
                  Company website
                  <input
                    type="text"
                    className={styles.fallbackInput}
                    placeholder="https://example.com"
                    value={fallbackWebsite}
                    onChange={(e) => setFallbackWebsite(e.target.value)}
                  />
                </label>
                <label className={styles.fallbackLabel}>
                  Company description
                  <textarea
                    className={styles.fallbackTextarea}
                    placeholder="Short description of what the company does..."
                    value={fallbackDescription}
                    onChange={(e) => setFallbackDescription(e.target.value)}
                    rows={3}
                  />
                </label>
                {fallbackError && (
                  <p className={styles.fallbackError}>{fallbackError}</p>
                )}
                <button
                  type="submit"
                  className={styles.fallbackButton}
                  disabled={fallbackSubmitting}
                >
                  {fallbackSubmitting ? "Submitting…" : "Submit"}
                </button>
              </form>
            </div>
          )}

          {/* Section list — shown when ready and company_id is resolved */}
          {isReady && project.company_id && (
            <div className={styles.sectionListSection}>
              <h2 className={styles.sectionListTitle}>Sections</h2>
              {sections.length > 0 ? (
                <ul className={styles.sectionList}>
                  {sections.map((s) => (
                    <li key={s.id} className={styles.sectionItem}>{s.title}</li>
                  ))}
                </ul>
              ) : (
                <p className={styles.message}>No sections available</p>
              )}
            </div>
          )}

          <div className={styles.generateSection}>
            <p className={styles.generateHint}>
              {isReady
                ? "Context is assembled. You can now generate a document."
                : "Generation will be available once context assembly is complete."}
            </p>
            <button
              className={styles.generateButton}
              disabled={!isReady}
              onClick={() =>
                project.company_id
                  ? navigate(`/editor/${String(project.company_id)}/vorhabensbeschreibung`)
                  : undefined
              }
            >
              Generate Document
            </button>
          </div>
        </div>

        {/* ── Context sidebar ── */}
        <aside className={styles.sidebar}>
          <h2 className={styles.sidebarTitle}>Context</h2>

          <div className={styles.contextItem}>
            <span className={styles.contextLabel}>Company</span>
            <span className={styles.contextValue}>
              {project.company_name ?? "—"}
            </span>
          </div>

          <div className={styles.contextItem}>
            <span className={styles.contextLabel}>Funding Program</span>
            <span className={styles.contextValue}>
              {project.funding_program_title ?? "—"}
            </span>
          </div>

          <div className={styles.contextItem}>
            <span className={styles.contextLabel}>Status</span>
            <span className={styles.contextValue}>{project.status}</span>
          </div>

          {/* Completeness score — shown only when score is available */}
          {ctx?.completeness_score != null && (
            <div className={styles.contextItem}>
              <span className={styles.contextLabel}>Context completeness</span>
              <div className={styles.completenessRow}>
                <div className={styles.completenessTrack}>
                  <div
                    className={styles.completenessFill}
                    style={{ width: `${ctx.completeness_score}%` }}
                  />
                </div>
                <span className={styles.completenessValue}>
                  {ctx.completeness_score}%
                </span>
              </div>
            </div>
          )}

          {ctx && (
            <div className={styles.contextItem}>
              <span className={styles.contextLabel}>Last assembled</span>
              <span className={styles.contextValue}>
                {new Date(ctx.updated_at).toLocaleString("de-DE")}
              </span>
            </div>
          )}

          <div className={styles.contextItem}>
            <span className={styles.contextLabel}>Created</span>
            <span className={styles.contextValue}>
              {new Date(project.created_at).toLocaleDateString("de-DE")}
            </span>
          </div>
        </aside>
      </div>
    </div>
  );
}
