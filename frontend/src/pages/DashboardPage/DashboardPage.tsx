import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../../utils/api";
import styles from "./DashboardPage.module.css";

interface ProjectListItem {
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
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, [showArchived]);

  async function fetchProjects() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<ProjectListItem[]>(
        `/projects?archived=${showArchived}`
      );
      setProjects(data);
    } catch {
      setError("Failed to load projects.");
    } finally {
      setLoading(false);
    }
  }

  const filtered = projects.filter((p) =>
    p.topic.toLowerCase().includes(search.toLowerCase())
  );

  function statusBadgeClass(status: string) {
    if (status === "ready") return styles.statusReady;
    if (status === "assembling") return styles.statusAssembling;
    if (status === "failed") return styles.statusFailed;
    return styles.statusPending;
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Projects</h1>
          <p className={styles.subtitle}>
            {showArchived ? "Archived projects" : "Your active projects"}
          </p>
        </div>
        <button
          className={styles.newButton}
          onClick={() => navigate("/projects/new")}
        >
          + New Project
        </button>
      </div>

      <div className={styles.toolbar}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search by topic..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          className={styles.archiveToggle}
          onClick={() => setShowArchived((v) => !v)}
        >
          {showArchived ? "Show Active" : "Show Archived"}
        </button>
      </div>

      {loading && <p className={styles.message}>Loading...</p>}
      {error && <p className={styles.errorMessage}>{error}</p>}

      {!loading && !error && filtered.length === 0 && (
        <div className={styles.empty}>
          <p>No projects found.</p>
          <button
            className={styles.newButton}
            onClick={() => navigate("/projects/new")}
          >
            Create your first project
          </button>
        </div>
      )}

      <div className={styles.grid}>
        {filtered.map((project) => (
          <div
            key={project.id}
            className={styles.card}
            onClick={() => navigate(`/projects/${project.id}`)}
          >
            <div className={styles.cardHeader}>
              <span className={`${styles.statusBadge} ${statusBadgeClass(project.status)}`}>
                {project.status}
              </span>
            </div>
            <p className={styles.cardTopic}>{project.topic}</p>
            <p className={styles.cardDetail}>
              {project.company_name ?? "—"} · {project.funding_program_title ?? "—"}
            </p>
            <p className={styles.cardMeta}>
              {new Date(project.created_at).toLocaleDateString("de-DE", {
                day: "2-digit",
                month: "short",
                year: "numeric",
              })}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
