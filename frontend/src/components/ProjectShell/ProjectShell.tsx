import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { apiGet } from "../../utils/api";
import CreateProjectModal from "../CreateProjectModal/CreateProjectModal";
import styles from "./ProjectShell.module.css";

interface ProjectListItem {
  id: string;
  topic: string;
  status: string;
  company_name: string | null;
  updated_at: string;
}

interface ProjectShellProps {
  children: ReactNode;
}

function statusBadgeClass(status: string): string {
  if (status === "complete") return styles.badgeComplete;
  if (status === "ready") return styles.badgeReady;
  if (status === "assembling" || status === "generating") return styles.badgeAssembling;
  if (status === "failed") return styles.badgeFailed;
  return styles.badgeAssembling;
}

function statusLabel(status: string): string {
  if (status === "complete") return "Generated";
  if (status === "ready") return "Ready";
  if (status === "assembling") return "Preparing...";
  if (status === "generating") return "Generating...";
  if (status === "failed") return "Failed";
  return status;
}

export default function ProjectShell({ children }: ProjectShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { id: activeProjectId } = useParams<{ id: string }>();
  const { logout, userEmail, isAdmin } = useAuth();

  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [search, setSearch] = useState("");
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, [location.pathname]);

  async function fetchProjects() {
    try {
      const data = await apiGet<ProjectListItem[]>("/projects?archived=false");
      setProjects(data);
    } catch {
      // non-fatal
    }
  }

  const filtered = projects.filter((p) =>
    p.topic.toLowerCase().includes(search.toLowerCase()) ||
    (p.company_name ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const getUserInitial = () => (userEmail ? userEmail.charAt(0).toUpperCase() : "U");

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const isProjectsActive = location.pathname === "/dashboard" || location.pathname.startsWith("/projects/");

  return (
    <div className={styles.shell}>
      {/* ── Icon rail ── */}
      <aside className={styles.iconRail}>
        <div className={styles.railTop}>
          <div className={styles.railLogoWrap}>
            <span className={styles.railLogoText}>I</span>
          </div>
          <Link
            to="/dashboard"
            className={`${styles.railIcon} ${isProjectsActive ? styles.railIconActive : ""}`}
            title="Projects"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
            </svg>
          </Link>
          {isAdmin && (
            <Link
              to="/admin/knowledge-base"
              className={`${styles.railIcon} ${location.pathname.startsWith("/admin") ? styles.railIconActive : ""}`}
              title="Knowledge Base"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </Link>
          )}
        </div>
        <div className={styles.railBottom}>
          <button className={styles.railAvatar} onClick={handleLogout} title={`Logout (${userEmail ?? ""})`}>
            {getUserInitial()}
          </button>
        </div>
      </aside>

      {/* ── Project list panel ── */}
      <div className={styles.projectPanel}>
        <p className={styles.panelLabel}>PROJECTS</p>

        <div className={styles.searchRow}>
          <div className={styles.searchWrap}>
            <svg className={styles.searchIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className={styles.projectList}>
          {filtered.map((p) => (
            <button
              key={p.id}
              className={`${styles.projectItem} ${p.id === activeProjectId ? styles.projectItemActive : ""}`}
              onClick={() => navigate(`/projects/${p.id}`)}
            >
              <span className={styles.projectCompany}>{p.company_name ?? p.topic}</span>
              <span className={styles.projectTopic}>{p.company_name ? p.topic : ""}</span>
              <span className={`${styles.projectBadge} ${statusBadgeClass(p.status)}`}>
                {statusLabel(p.status)}
              </span>
            </button>
          ))}
        </div>

        <div className={styles.panelFooter}>
          <button className={styles.newProjectBtn} onClick={() => setShowModal(true)}>
            + New Project
          </button>
          <div className={styles.userRow}>
            <div className={styles.userAvatar}>{getUserInitial()}</div>
            <div className={styles.userInfo}>
              <span className={styles.userName}>{userEmail?.split("@")[0] ?? "User"}</span>
              <span className={styles.userEmail}>{userEmail ?? ""}</span>
            </div>
            <button className={styles.logoutBtn} onClick={handleLogout} title="Logout">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* ── Main content ── */}
      <main className={styles.content}>{children}</main>

      {showModal && (
        <CreateProjectModal
          onClose={() => setShowModal(false)}
          onCreated={(projectId) => {
            setShowModal(false);
            fetchProjects();
            navigate(`/projects/${projectId}`);
          }}
        />
      )}
    </div>
  );
}
