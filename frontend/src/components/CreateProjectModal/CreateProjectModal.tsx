import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../../utils/api";
import styles from "./CreateProjectModal.module.css";

interface FundingProgram {
  id: number;
  title: string;
}

interface ProjectResponse {
  id: string;
}

interface CreateProjectModalProps {
  onClose: () => void;
  onCreated: (projectId: string) => void;
}

export default function CreateProjectModal({ onClose, onCreated }: CreateProjectModalProps) {
  const [fundingPrograms, setFundingPrograms] = useState<FundingProgram[]>([]);
  const [fundingProgramId, setFundingProgramId] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [topic, setTopic] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<FundingProgram[]>("/funding-programs").then(setFundingPrograms).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) {
      setError("Project topic is required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const project = await apiPost<ProjectResponse>("/projects", {
        company_name: companyName.trim() || null,
        funding_program_id: fundingProgramId ? Number(fundingProgramId) : null,
        topic: topic.trim(),
      });
      onCreated(project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h2 className={styles.title}>Create New Project</h2>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <label className={styles.label}>
            Company Name
            <input
              type="text"
              className={styles.input}
              placeholder="e.g. TechVentures GmbH"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              autoFocus
            />
          </label>

          <label className={styles.label}>
            Funding Program
            <select
              className={styles.select}
              value={fundingProgramId}
              onChange={(e) => setFundingProgramId(e.target.value)}
            >
              <option value="">Select a funding program</option>
              {fundingPrograms.map((fp) => (
                <option key={fp.id} value={String(fp.id)}>{fp.title}</option>
              ))}
            </select>
          </label>

          <label className={styles.label}>
            Project Topic <span className={styles.required}>*</span>
            <textarea
              className={styles.textarea}
              placeholder="Describe your project topic..."
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              rows={3}
            />
          </label>

          {error && <p className={styles.error}>{error}</p>}

          <button type="submit" className={styles.submitBtn} disabled={submitting}>
            {submitting ? "Creating..." : "Create Project"}
          </button>
        </form>
      </div>
    </div>
  );
}
