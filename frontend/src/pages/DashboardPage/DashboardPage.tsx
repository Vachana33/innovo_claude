import { useState } from "react";
import { useNavigate } from "react-router-dom";
import CreateProjectModal from "../../components/CreateProjectModal/CreateProjectModal";
import styles from "./DashboardPage.module.css";

export default function DashboardPage() {
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);

  return (
    <div className={styles.container}>
      <div className={styles.empty}>
        <div className={styles.emptyIconWrap}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <h2 className={styles.emptyTitle}>No Project Selected</h2>
        <p className={styles.emptyHint}>
          Select a project from the sidebar or create a new one to start generating your Vorhabensbeschreibung.
        </p>
        <button className={styles.createBtn} onClick={() => setShowModal(true)}>
          + Create New Project
        </button>
      </div>

      {showModal && (
        <CreateProjectModal
          onClose={() => setShowModal(false)}
          onCreated={(projectId) => {
            setShowModal(false);
            navigate(`/projects/${projectId}`);
          }}
        />
      )}
    </div>
  );
}
