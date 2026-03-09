import { useState, useEffect } from "react";
import styles from "./MilestoneTable.module.css";

interface Milestone {
  milestone_number: number;
  expected_target: string;
  target_date: string; // DD.MM.YYYY format
  expected_expenditure: number; // EUR
}

interface MilestoneData {
  milestones: Milestone[];
  total_expenditure: number | null;
}

interface MilestoneTableProps {
  sectionId: string;
  content: string;
  onContentChange: (content: string) => void;
}

export default function MilestoneTable({ content, onContentChange }: MilestoneTableProps) {
  const [milestoneData, setMilestoneData] = useState<MilestoneData>({
    milestones: [],
    total_expenditure: null
  });

  // Parse content on mount and when content prop changes
  useEffect(() => {
    try {
      if (content && content.trim()) {
        const parsed = JSON.parse(content);
        setMilestoneData({
          milestones: parsed.milestones || [],
          total_expenditure: parsed.total_expenditure || null
        });
      } else {
        setMilestoneData({
          milestones: [],
          total_expenditure: null
        });
      }
    } catch (e) {
      console.error("Failed to parse milestone data:", e);
      setMilestoneData({
        milestones: [],
        total_expenditure: null
      });
    }
  }, [content]);

  // Calculate total expenditure whenever milestones change
  useEffect(() => {
    const total = milestoneData.milestones.reduce((sum, m) => sum + (m.expected_expenditure || 0), 0);
    const newData = {
      ...milestoneData,
      total_expenditure: total > 0 ? total : null
    };
    
    // Only update if total changed to avoid infinite loop
    if (newData.total_expenditure !== milestoneData.total_expenditure) {
      setMilestoneData(newData);
      // Save to content
      onContentChange(JSON.stringify(newData));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [milestoneData.milestones]);

  const addMilestone = () => {
    const newMilestone: Milestone = {
      milestone_number: milestoneData.milestones.length + 1,
      expected_target: "",
      target_date: "",
      expected_expenditure: 0
    };
    setMilestoneData({
      ...milestoneData,
      milestones: [...milestoneData.milestones, newMilestone]
    });
  };

  const removeMilestone = (index: number) => {
    const newMilestones = milestoneData.milestones.filter((_, i) => i !== index);
    // Renumber milestones
    const renumbered = newMilestones.map((m, i) => ({
      ...m,
      milestone_number: i + 1
    }));
    setMilestoneData({
      ...milestoneData,
      milestones: renumbered
    });
  };

  const updateMilestone = (index: number, field: keyof Milestone, value: string | number) => {
    const newMilestones = [...milestoneData.milestones];
    newMilestones[index] = {
      ...newMilestones[index],
      [field]: value
    };
    setMilestoneData({
      ...milestoneData,
      milestones: newMilestones
    });
  };

  const formatDate = (dateStr: string): string => {
    // Ensure DD.MM.YYYY format
    if (!dateStr) return "";
    // If user types YYYY-MM-DD, convert to DD.MM.YYYY
    if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
      const [year, month, day] = dateStr.split("-");
      return `${day}.${month}.${year}`;
    }
    return dateStr;
  };

  return (
    <div className={styles.milestoneTableContainer}>
      <table className={styles.milestoneTable}>
        <thead>
          <tr>
            <th>Meilenstein</th>
            <th>erwartetes Ziel</th>
            <th>erwarteter Zeitpunkt der Zielerreichung (TT.MM.JJJJ)</th>
            <th>erwartete Ausgaben zum Zeitpunkt der Zielerreichung (EUR)</th>
          </tr>
        </thead>
        <tbody>
          {milestoneData.milestones.map((milestone, index) => (
            <tr key={index}>
              <td>{milestone.milestone_number}</td>
              <td>
                <input
                  type="text"
                  value={milestone.expected_target}
                  onChange={(e) => updateMilestone(index, "expected_target", e.target.value)}
                  placeholder="Ziel beschreiben"
                  className={styles.inputField}
                />
              </td>
              <td>
                <input
                  type="text"
                  value={milestone.target_date}
                  onChange={(e) => {
                    const formatted = formatDate(e.target.value);
                    updateMilestone(index, "target_date", formatted);
                  }}
                  placeholder="DD.MM.YYYY"
                  className={styles.inputField}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={milestone.expected_expenditure || ""}
                  onChange={(e) => updateMilestone(index, "expected_expenditure", parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                  className={styles.inputField}
                />
              </td>
              <td>
                <button
                  onClick={() => removeMilestone(index)}
                  className={styles.removeButton}
                  aria-label="Remove milestone"
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
          <tr className={styles.totalRow}>
            <td colSpan={2}></td>
            <td className={styles.totalLabel}>erwartete Gesamtausgaben</td>
            <td className={styles.totalValue}>
              {milestoneData.total_expenditure !== null
                ? new Intl.NumberFormat("de-DE", {
                    style: "currency",
                    currency: "EUR",
                    minimumFractionDigits: 2
                  }).format(milestoneData.total_expenditure)
                : "0,00 €"}
            </td>
            <td></td>
          </tr>
        </tbody>
      </table>
      <button onClick={addMilestone} className={styles.addButton}>
        + Meilenstein hinzufügen
      </button>
    </div>
  );
}
