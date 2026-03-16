import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../../utils/api";
import styles from "./NewProjectPage.module.css";

interface FundingProgram {
  id: number;
  title: string;
}

interface ProjectResponse {
  id: string;
}

export default function NewProjectPage() {
  const navigate = useNavigate();

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
      setError("Topic is required.");
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
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.backRow}>
          <button className={styles.backButton} onClick={() => navigate("/dashboard")}>
            ← Back
          </button>
        </div>

        <h1 className={styles.title}>New Project</h1>
        <p className={styles.subtitle}>
          Enter the company name, select a funding program, and describe what you want to generate.
          The system will research the company automatically.
        </p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <label className={styles.label}>
            Company Name
            <input
              type="text"
              className={styles.input}
              placeholder="e.g. Siemens Energy GmbH"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
            />
          </label>

          <label className={styles.label}>
            Funding Program
            <select
              className={styles.select}
              value={fundingProgramId}
              onChange={(e) => setFundingProgramId(e.target.value)}
            >
              <option value="">— Select a funding program (optional) —</option>
              {fundingPrograms.map((fp) => (
                <option key={fp.id} value={String(fp.id)}>
                  {fp.title}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.label}>
            Topic <span className={styles.required}>*</span>
            <textarea
              className={styles.textarea}
              placeholder="Describe the purpose or goal of this funding application..."
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              rows={4}
            />
          </label>

          {error && <p className={styles.error}>{error}</p>}

          <button
            type="submit"
            className={styles.submitButton}
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Start Analysis"}
          </button>
        </form>
      </div>
    </div>
  );
}
