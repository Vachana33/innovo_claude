import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../utils/api";
import styles from "./TemplateEditorPage.module.css";

type Section = {
  id: string;
  title: string;
  type?: "text" | "milestone_table";
  content?: string;
};

type UserTemplate = {
  id: string;
  name: string;
  description?: string;
  template_structure: {
    sections: Section[];
  };
  created_at: string;
  updated_at: string;
};

export default function TemplateEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditMode = !!id;

  const [templateName, setTemplateName] = useState("");
  const [templateDescription, setTemplateDescription] = useState("");
  const [sections, setSections] = useState<Section[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [editingSectionId, setEditingSectionId] = useState<string | null>(null);
  const [editingSectionTitle, setEditingSectionTitle] = useState("");
  const [showAddSectionMenu, setShowAddSectionMenu] = useState<string | null>(null);

  // Load template if editing
  useEffect(() => {
    if (isEditMode) {
      loadTemplate();
    } else {
      setIsLoading(false);
    }
  }, [id]);

  async function loadTemplate() {
    if (!id) return;
    try {
      setIsLoading(true);
      const template: UserTemplate = await apiGet(`/user-templates/${id}`);
      setTemplateName(template.name);
      setTemplateDescription(template.description || "");
      setSections(template.template_structure.sections || []);
    } catch (error: unknown) {
      console.error("Error loading template:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to load template";
      alert(errorMsg);
      navigate("/projects");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSave() {
    if (!templateName.trim()) {
      alert("Template name is required");
      return;
    }

    setIsSaving(true);
    try {
      const templateData = {
        name: templateName.trim(),
        description: templateDescription.trim() || null,
        sections: sections.map(s => ({
          id: s.id,
          title: s.title,
          content: s.content || "",
          type: s.type || "text"
        }))
      };

      if (isEditMode && id) {
        await apiPut(`/user-templates/${id}`, templateData);
      } else {
        await apiPost("/user-templates", templateData);
      }

      alert("Template saved successfully!");
      navigate("/projects");
    } catch (error: unknown) {
      console.error("Error saving template:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to save template";
      alert(errorMsg);
    } finally {
      setIsSaving(false);
    }
  }

  function generateNewSectionId(currentSectionId: string, isMainSection: boolean): string {
    if (isMainSection) {
      const topLevelSections = sections.filter(s => s.id.split('.').length === 1);
      const maxNumber = topLevelSections.reduce((max, s) => {
        const num = parseInt(s.id, 10);
        return num > max ? num : max;
      }, 0);
      return (maxNumber + 1).toString();
    } else {
      const parts = currentSectionId.split('.');
      const parentId = parts.length === 1 ? currentSectionId : parts.slice(0, -1).join('.');
      const targetDepth = parts.length === 1 ? 2 : parts.length;
      
      const subSections = sections.filter(s => {
        const sParts = s.id.split('.');
        return sParts.length === targetDepth && 
               sParts.slice(0, -1).join('.') === parentId;
      });
      
      const maxNumber = subSections.reduce((max, s) => {
        const lastPart = parseInt(s.id.split('.').pop() || '0', 10);
        return lastPart > max ? lastPart : max;
      }, 0);
      
      return `${parentId}.${maxNumber + 1}`;
    }
  }

  function handleAddSectionBelow(sectionId: string, isMainSection: boolean) {
    const currentIndex = sections.findIndex(s => s.id === sectionId);
    if (currentIndex === -1) return;

    const newSectionId = generateNewSectionId(sectionId, isMainSection);
    const newSection: Section = {
      id: newSectionId,
      title: `${newSectionId}. `,
      content: "",
      type: "text"
    };

    const updatedSections = [
      ...sections.slice(0, currentIndex + 1),
      newSection,
      ...sections.slice(currentIndex + 1)
    ];

    setSections(updatedSections);
    setShowAddSectionMenu(null);
    setEditingSectionId(newSectionId);
    setEditingSectionTitle(newSection.title);
  }

  function handleDeleteSection(sectionId: string) {
    if (!confirm("Delete this section?")) return;
    
    let updatedSections = sections.filter(s => s.id !== sectionId);
    updatedSections = updatedSections.filter(s => !s.id.startsWith(sectionId + "."));
    
    // Renumber sections
    updatedSections = renumberSections(updatedSections);
    setSections(updatedSections);
  }

  function renumberSections(sections: Section[]): Section[] {
    if (sections.length === 0) return [];
    
    const sorted = [...sections].sort((a, b) => {
      const aParts = a.id.split('.').map(Number);
      const bParts = b.id.split('.').map(Number);
      for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
        const aVal = aParts[i] || 0;
        const bVal = bParts[i] || 0;
        if (aVal !== bVal) return aVal - bVal;
      }
      return 0;
    });
    
    const renumbered: Section[] = [];
    const parentCounters: Record<string, number> = {};
    
    sorted.forEach(section => {
      const parts = section.id.split('.');
      const level = parts.length;
      
      if (level === 1) {
        const counter = (parentCounters[''] || 0) + 1;
        parentCounters[''] = counter;
        const newId = counter.toString();
        const titleWithoutNumber = section.title.replace(/^\d+\.\s*/, '');
        renumbered.push({
          ...section,
          id: newId,
          title: `${newId}. ${titleWithoutNumber}`
        });
        parentCounters[newId] = 0;
      } else {
        const oldParentId = parts.slice(0, -1).join('.');
        const parentCounter = parentCounters[oldParentId] || 0;
        const counter = parentCounter + 1;
        parentCounters[oldParentId] = counter;
        const newId = `${oldParentId}.${counter}`;
        const titleWithoutNumber = section.title.replace(/^[\d.]+\.\s*/, '');
        renumbered.push({
          ...section,
          id: newId,
          title: `${newId}. ${titleWithoutNumber}`
        });
        parentCounters[newId] = 0;
      }
    });
    
    return renumbered;
  }

  function handleStartRenameSection(section: Section) {
    setEditingSectionId(section.id);
    setEditingSectionTitle(section.title);
  }

  function handleSaveRenameSection(sectionId: string) {
    const updatedSections = sections.map(s => 
      s.id === sectionId 
        ? { ...s, title: editingSectionTitle }
        : s
    );
    setSections(updatedSections);
    setEditingSectionId(null);
    setEditingSectionTitle("");
  }

  function handleCancelRename() {
    setEditingSectionId(null);
    setEditingSectionTitle("");
  }

  function handleMoveSection(sectionId: string, direction: "up" | "down") {
    const currentIndex = sections.findIndex(s => s.id === sectionId);
    if (currentIndex === -1) return;

    const newIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    if (newIndex < 0 || newIndex >= sections.length) return;

    const updatedSections = [...sections];
    [updatedSections[currentIndex], updatedSections[newIndex]] = 
      [updatedSections[newIndex], updatedSections[currentIndex]];

    // Renumber after reordering
    const renumbered = renumberSections(updatedSections);
    setSections(renumbered);
  }

  function handleAddMilestoneTable(sectionId: string) {
    const currentIndex = sections.findIndex(s => s.id === sectionId);
    if (currentIndex === -1) return;

    const newSectionId = generateNewSectionId(sectionId, false);
    const newSection: Section = {
      id: newSectionId,
      title: `${newSectionId}. Meilensteinplanung`,
      content: JSON.stringify({
        milestones: [],
        total_expenditure: null
      }),
      type: "milestone_table"
    };

    const updatedSections = [
      ...sections.slice(0, currentIndex + 1),
      newSection,
      ...sections.slice(currentIndex + 1)
    ];

    setSections(updatedSections);
    setShowAddSectionMenu(null);
  }

  if (isLoading) {
    return <div className={styles.container}>Loading...</div>;
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>{isEditMode ? "Edit Template" : "New Template"}</h1>
        <div className={styles.headerActions}>
          <button
            onClick={() => navigate("/projects")}
            className={styles.cancelBtn}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className={styles.saveBtn}
          >
            {isSaving ? "Saving..." : "Save Template"}
          </button>
        </div>
      </div>

      <div className={styles.form}>
        <div className={styles.formGroup}>
          <label>Template Name *</label>
          <input
            type="text"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            placeholder="e.g., Standard Vorhabensbeschreibung"
            className={styles.input}
          />
        </div>

        <div className={styles.formGroup}>
          <label>Description (optional)</label>
          <textarea
            value={templateDescription}
            onChange={(e) => setTemplateDescription(e.target.value)}
            placeholder="Brief description of this template"
            className={styles.textarea}
            rows={3}
          />
        </div>

        <div className={styles.formGroup}>
          <label>Sections</label>
          <div className={styles.sectionsList}>
            {sections.length === 0 ? (
              <div className={styles.emptyState}>
                <p>No sections yet. Add your first section below.</p>
                <button
                  onClick={() => {
                    const firstSection: Section = {
                      id: "1",
                      title: "1. ",
                      content: "",
                      type: "text"
                    };
                    setSections([firstSection]);
                    setEditingSectionId("1");
                    setEditingSectionTitle("1. ");
                  }}
                  className={styles.addFirstBtn}
                >
                  + Add First Section
                </button>
              </div>
            ) : (
              sections.map((s) => {
                const depth = s.id.split(".").length;
                const isTopLevel = depth === 1;
                const isEditing = editingSectionId === s.id;
                const currentIndex = sections.findIndex(sec => sec.id === s.id);

                return (
                  <div
                    key={s.id}
                    className={`${styles.sectionBlock} ${isTopLevel ? styles.sectionLevel1 : styles.sectionLevel2}`}
                  >
                    <div className={styles.sectionHeader}>
                      <span className={styles.sectionNumber}>{s.id}.</span>
                      {isEditing ? (
                        <>
                          <input
                            type="text"
                            value={editingSectionTitle}
                            onChange={(e) => setEditingSectionTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                handleSaveRenameSection(s.id);
                              } else if (e.key === "Escape") {
                                handleCancelRename();
                              }
                            }}
                            autoFocus
                            className={styles.renameInput}
                          />
                          <button
                            onClick={() => handleSaveRenameSection(s.id)}
                            className={styles.iconBtn}
                          >
                            ✓
                          </button>
                          <button
                            onClick={handleCancelRename}
                            className={styles.iconBtn}
                          >
                            ✕
                          </button>
                        </>
                      ) : (
                        <>
                          <span className={styles.sectionTitle}>
                            {s.title.replace(/^[\d.]+\.\s*/, "")}
                          </span>
                          <div className={styles.sectionActions}>
                            <button
                              onClick={() => handleStartRenameSection(s)}
                              className={styles.iconBtn}
                              title="Rename"
                            >
                              ✏️
                            </button>
                            <button
                              onClick={() => handleMoveSection(s.id, "up")}
                              disabled={currentIndex === 0}
                              className={styles.iconBtn}
                              title="Move up"
                            >
                              ↑
                            </button>
                            <button
                              onClick={() => handleMoveSection(s.id, "down")}
                              disabled={currentIndex === sections.length - 1}
                              className={styles.iconBtn}
                              title="Move down"
                            >
                              ↓
                            </button>
                            <button
                              onClick={() => handleDeleteSection(s.id)}
                              className={styles.iconBtn}
                              title="Delete"
                            >
                              ❌
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                    {s.type === "milestone_table" && (
                      <div className={styles.milestoneBadge}>
                        Milestone Table
                      </div>
                    )}
                    {showAddSectionMenu === s.id ? (
                      <div className={styles.addMenu}>
                        <button
                          onClick={() => handleAddSectionBelow(s.id, true)}
                          className={styles.addMenuBtn}
                        >
                          + Main Section
                        </button>
                        <button
                          onClick={() => handleAddSectionBelow(s.id, false)}
                          className={styles.addMenuBtn}
                        >
                          + Sub-section
                        </button>
                        <button
                          onClick={() => handleAddMilestoneTable(s.id)}
                          className={styles.addMenuBtn}
                        >
                          + Milestone Table
                        </button>
                        <button
                          onClick={() => setShowAddSectionMenu(null)}
                          className={styles.addMenuBtn}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setShowAddSectionMenu(s.id)}
                        className={styles.addBelowBtn}
                      >
                        + Add section below
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
