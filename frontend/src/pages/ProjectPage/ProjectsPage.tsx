import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { apiGet, apiPost, apiPut, apiDelete, apiUploadFile } from "../../utils/api";
import styles from "./ProjectsPage.module.css";

type FundingProgram = {
  id: number;
  title: string;
  website?: string;
  template_name?: string; // Legacy field
  template_source?: "system" | "user";
  template_ref?: string;
  // Scraped data fields
  description?: string;
  sections_json?: Array<Record<string, unknown>>;
  content_hash?: string;
  last_scraped_at?: string;
};

type Company = {
  id: number;
  name: string;
  website?: string;
  audio_path?: string;
  created_at: string;
};

type DocType = "vorhaben" | "vorkalkulation";

export default function ProjectsPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();

  // Handle logout: clear auth state and redirect to login
  function handleLogout() {
    logout(); // Clear token and auth state
    navigate("/login", { replace: true }); // Redirect to login page
  }

  // Funding programs from backend
  const [programs, setPrograms] = useState<FundingProgram[]>([]);
  const [isLoadingPrograms, setIsLoadingPrograms] = useState(true);
  
  // Companies - empty initially, fetched based on selected program
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoadingCompanies, setIsLoadingCompanies] = useState(false);

  const [selectedProgramId, setSelectedProgramId] = useState<number | null>(
    null
  );
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(
    null
  );

  // Sidebar tab state
  const [activeTab, setActiveTab] =
    useState<"funding" | "without" | "collab">("funding");

  // Reset search terms when switching tabs
  useEffect(() => {
    setProgramSearchTerm("");
    setCompanySearchTerm("");
  }, [activeTab]);

  // Dialog states
  const [showProgramDialog, setShowProgramDialog] = useState(false);
  const [showCompanyDialog, setShowCompanyDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [showCompanyMenu, setShowCompanyMenu] = useState(false);
  
  // Edit/Delete states
  const [editingProgramId, setEditingProgramId] = useState<number | null>(null);
  const [deletingProgramId, setDeletingProgramId] = useState<number | null>(null);
  const [editingCompanyId, setEditingCompanyId] = useState<number | null>(null);
  const [deletingCompanyId, setDeletingCompanyId] = useState<number | null>(null);
  const [openProgramMenuId, setOpenProgramMenuId] = useState<number | null>(null);
  const [openCompanyMenuId, setOpenCompanyMenuId] = useState<number | null>(null);
  const [scrapingProgramId, setScrapingProgramId] = useState<number | null>(null);
  
  // Import dialog state
  const [allCompanies, setAllCompanies] = useState<Company[]>([]);
  const [isLoadingAllCompanies, setIsLoadingAllCompanies] = useState(false);
  const [isCreatingCompany, setIsCreatingCompany] = useState(false);
  const [isImportingCompany, setIsImportingCompany] = useState(false);
  const [isUpdatingProgram, setIsUpdatingProgram] = useState(false);
  const [isDeletingProgram, setIsDeletingProgram] = useState(false);
  const [isUpdatingCompany, setIsUpdatingCompany] = useState(false);
  const [isDeletingCompany, setIsDeletingCompany] = useState(false);

  // Form fields
  const [programTitle, setProgramTitle] = useState("");
  const [programWebsite, setProgramWebsite] = useState("");
  const [programTemplate, setProgramTemplate] = useState<string>("");
  const [programTemplateSource, setProgramTemplateSource] = useState<"system" | "user" | "">("");
  const [availableTemplates, setAvailableTemplates] = useState<{
    system: Array<{ id: string; name: string; source: string }>;
    user: Array<{ id: string; name: string; source: string; description?: string }>;
  }>({ system: [], user: [] });
  const [companyName, setCompanyName] = useState("");
  const [companyWebsite, setCompanyWebsite] = useState("");
  const [companyAudio, setCompanyAudio] = useState<File | null>(null);
  // Reserved for future use - companyDocs is set but not currently read
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_companyDocs, setCompanyDocs] = useState<FileList | null>(null);
  const [isCreatingProgram, setIsCreatingProgram] = useState(false);

  // Search functionality - client-side filtering
  const [programSearchTerm, setProgramSearchTerm] = useState("");
  const [companySearchTerm, setCompanySearchTerm] = useState("");

  // Filter programs based on search term (case-insensitive)
  const filteredPrograms = programs.filter((p) => {
    if (!programSearchTerm.trim()) return true;
    const searchLower = programSearchTerm.toLowerCase();
    return (
      p.title.toLowerCase().includes(searchLower) ||
      (p.website && p.website.toLowerCase().includes(searchLower))
    );
  });

  // Filter companies based on search term (case-insensitive)
  const filteredCompanies = companies.filter((c) => {
    if (!companySearchTerm.trim()) return true;
    const searchLower = companySearchTerm.toLowerCase();
    return (
      c.name.toLowerCase().includes(searchLower) ||
      (c.website && c.website.toLowerCase().includes(searchLower))
    );
  });

  // Fetch funding programs on component mount
  useEffect(() => {
    async function fetchPrograms() {
      try {
        setIsLoadingPrograms(true);
        const data = await apiGet<FundingProgram[]>("/funding-programs");
        setPrograms(data);
      } catch (error: unknown) {
        console.error("Error fetching funding programs:", error);
        if (error instanceof Error && error.message.includes("Authentication required")) {
          logout();
        }
      } finally {
        setIsLoadingPrograms(false);
      }
    }
    fetchPrograms();
  }, [logout]);

  // Fetch available templates when dialog opens
  useEffect(() => {
    if (showProgramDialog) {
      fetchAvailableTemplates();
    } else {
      // Reset templates when dialog closes
      setAvailableTemplates({ system: [], user: [] });
    }
  }, [showProgramDialog]);

  async function fetchAvailableTemplates() {
    try {
      const templates = await apiGet<{
        system: Array<{ id: string; name: string; source: string }>;
        user: Array<{ id: string; name: string; source: string; description?: string }>;
      }>("/templates/list");
      setAvailableTemplates(templates);
    } catch (error: unknown) {
      console.error("Error fetching templates:", error);
      // Don't show error to user, just use empty list
      setAvailableTemplates({ system: [], user: [] });
    }
  }

  // Fetch companies when a funding program is selected
  // ONLY uses GET /funding-programs/{id}/companies
  // NEVER calls GET /companies
  useEffect(() => {
    if (!selectedProgramId) {
      // Clear companies when no program is selected
      setCompanies([]);
      setSelectedCompanyId(null);
      return;
    }

    async function fetchCompanies() {
      try {
        setIsLoadingCompanies(true);
        // ONLY fetch from program-specific endpoint
        const data = await apiGet<Company[]>(
          `/funding-programs/${selectedProgramId}/companies`
        );
        // REPLACE entire list - do NOT append or merge
        setCompanies(data);
        // Clear selected company when switching programs
        setSelectedCompanyId(null);
      } catch (error: unknown) {
        console.error("Error fetching companies:", error);
        setCompanies([]);
        if (error instanceof Error && error.message.includes("Authentication required")) {
          logout();
        }
      } finally {
        setIsLoadingCompanies(false);
      }
    }
    fetchCompanies();
  }, [selectedProgramId, logout]);

  // Navigate to editor page
  function handleOpenEditor(docType: DocType) {
    if (!selectedProgramId || !selectedCompanyId) return;
    const company = companies.find((c) => c.id === selectedCompanyId);
    if (!company) return;
    // Use company ID and pass funding_program_id as query parameter
    navigate(`/editor/${selectedCompanyId}/${docType}?funding_program_id=${selectedProgramId}`);
  }

  // Create a new funding program
  async function handleCreateProgram(e: React.FormEvent) {
    e.preventDefault();
    if (!programTitle.trim()) return;

    setIsCreatingProgram(true);

    try {
      // Determine template_source and template_ref based on selection
      let templateSource: "system" | "user" | undefined = undefined;
      let templateRef: string | undefined = undefined;

      if (programTemplateSource === "system" && programTemplate) {
        templateSource = "system";
        templateRef = programTemplate;
      } else if (programTemplateSource === "user" && programTemplate) {
        templateSource = "user";
        templateRef = programTemplate;
      }

      const createdProgram = await apiPost<FundingProgram>("/funding-programs", {
        title: programTitle.trim(),
        website: programWebsite.trim() || undefined,
        template_source: templateSource,
        template_ref: templateRef,
        template_name: programTemplate || undefined, // Legacy field for backward compatibility
      });

      // Update state with the new program from backend
      setPrograms((prev) => [...prev, createdProgram]);

      // Auto-select the newly created program
      setSelectedProgramId(createdProgram.id);

      // Clear form and close dialog
      setProgramTitle("");
      setProgramWebsite("");
      setProgramTemplate("");
      setProgramTemplateSource("");
      setShowProgramDialog(false);
    } catch (error: unknown) {
      console.error("Error creating funding program:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to create funding program. Please try again.";
      alert(errorMsg);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsCreatingProgram(false);
    }
  }

  // Edit funding program
  async function handleUpdateProgram(e: React.FormEvent) {
    e.preventDefault();
    if (!editingProgramId || !programTitle.trim()) return;

    setIsUpdatingProgram(true);

    try {
      // Determine template_source and template_ref based on selection
      let templateSource: "system" | "user" | undefined = undefined;
      let templateRef: string | undefined = undefined;
      
      if (programTemplateSource === "system" && programTemplate) {
        templateSource = "system";
        templateRef = programTemplate;
      } else if (programTemplateSource === "user" && programTemplate) {
        templateSource = "user";
        templateRef = programTemplate;
      }
      
      const updatedProgram = await apiPut<FundingProgram>(
        `/funding-programs/${editingProgramId}`,
        {
          title: programTitle.trim(),
          website: programWebsite.trim() || undefined,
          template_source: templateSource,
          template_ref: templateRef,
          template_name: programTemplate || undefined, // Legacy field for backward compatibility
        }
      );

      // Replace program in list
      setPrograms((prev) =>
        prev.map((p) => (p.id === editingProgramId ? updatedProgram : p))
      );

      // Keep selection if same program
      if (selectedProgramId === editingProgramId) {
        // Refresh companies if program was selected
        const companiesData = await apiGet<Company[]>(
          `/funding-programs/${editingProgramId}/companies`
        );
        setCompanies(companiesData);
      }

      // Clear form and close dialog
      setProgramTitle("");
      setProgramWebsite("");
      setProgramTemplate("");
      setProgramTemplateSource("");
      setEditingProgramId(null);
      setShowProgramDialog(false);
    } catch (error: unknown) {
      console.error("Error updating funding program:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to update funding program. Please try again.";
      alert(errorMsg);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsUpdatingProgram(false);
    }
  }

  // Delete funding program
  async function handleDeleteProgram() {
    if (!deletingProgramId) return;

    setIsDeletingProgram(true);

    try {
      await apiDelete(`/funding-programs/${deletingProgramId}`);

      // Remove program from list
      setPrograms((prev) => prev.filter((p) => p.id !== deletingProgramId));

      // Clear selection if it was selected
      if (selectedProgramId === deletingProgramId) {
        setSelectedProgramId(null);
        setCompanies([]);
        setSelectedCompanyId(null);
      }

      // Close confirmation dialog
      setDeletingProgramId(null);
    } catch (error: unknown) {
      console.error("Error deleting funding program:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to delete funding program. Please try again.";
      alert(errorMsg);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsDeletingProgram(false);
    }
  }

  // Refresh funding program data (only if content changed)
  async function handleRefreshProgram(programId: number) {
    try {
      setScrapingProgramId(programId);
      const updated = await apiPost<FundingProgram>(
        `/funding-programs/${programId}/refresh`
      );

      // Refresh the programs list
      const data = await apiGet<FundingProgram[]>("/funding-programs");
      setPrograms(data);

      // Check if content changed
      const program = programs.find(p => p.id === programId);
      if (program?.content_hash === updated.content_hash) {
        alert("No changes detected. Website content is up to date.");
      } else {
        const sectionsCount = updated.sections_json?.length || 0;
        alert(`Data refreshed! Found ${sectionsCount} section${sectionsCount !== 1 ? 's' : ''}.`);
      }
    } catch (error: unknown) {
      console.error("Error refreshing program:", error);
      const errorMsg = error instanceof Error ? error.message : "Unknown error";
      alert(`Refresh failed: ${errorMsg}`);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setScrapingProgramId(null);
      setOpenProgramMenuId(null);
    }
  }

  // Create a new company in the selected funding program
  async function handleCreateCompany(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProgramId || !companyName.trim()) return;

    setIsCreatingCompany(true);

    try {
      // First, upload audio file if provided
      let audioPath: string | undefined = undefined;
      if (companyAudio) {
        const uploadData = await apiUploadFile("/upload-audio", companyAudio) as { audio_path?: string };
        audioPath = uploadData.audio_path;
      }

      // Then create the company with the audio path
      const createdCompany = await apiPost<Company>(
        `/funding-programs/${selectedProgramId}/companies`,
        {
          name: companyName.trim(),
          website: companyWebsite.trim() || undefined,
          audio_path: audioPath,
        }
      );

      // Add to current companies list (from backend response)
      setCompanies((prev) => [...prev, createdCompany]);

      // Auto-select the newly created company
      setSelectedCompanyId(createdCompany.id);

      // Clear form and close dialog
      setCompanyName("");
      setCompanyWebsite("");
      setCompanyAudio(null);
      setCompanyDocs(null);
      setShowCompanyDialog(false);
      setShowCompanyMenu(false);
    } catch (error: unknown) {
      console.error("Error creating company:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to create company. Please try again.";
      alert(errorMsg);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsCreatingCompany(false);
    }
  }

  // Fetch all companies for import dialog
  useEffect(() => {
    async function fetchAllCompanies() {
      if (!showImportDialog) return;

      try {
        setIsLoadingAllCompanies(true);
        const data = await apiGet<Company[]>("/companies");
        setAllCompanies(data);
      } catch (error: unknown) {
        console.error("Error fetching all companies:", error);
        setAllCompanies([]);
        if (error instanceof Error && error.message.includes("Authentication required")) {
          logout();
        }
      } finally {
        setIsLoadingAllCompanies(false);
      }
    }
    fetchAllCompanies();
  }, [showImportDialog, logout]);

  // Import an existing company into the funding program
  async function handleImportCompany(companyId: number) {
    if (!selectedProgramId) return;

    // Check if company is already in the list
    if (companies.some((c) => c.id === companyId)) {
      alert("This company is already linked to this funding program.");
      return;
    }

    setIsImportingCompany(true);

    try {
      const importedCompany = await apiPost<Company>(
        `/funding-programs/${selectedProgramId}/companies/${companyId}`
      );

      // Add to current companies list (from backend response)
      setCompanies((prev) => [...prev, importedCompany]);

      // Auto-select the imported company
      setSelectedCompanyId(importedCompany.id);

      // Close import dialog
      setShowImportDialog(false);
      setShowCompanyMenu(false);
    } catch (error: unknown) {
      console.error("Error importing company:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to import company. Please try again.";
      alert(errorMsg);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsImportingCompany(false);
    }
  }

  // Edit company
  async function handleUpdateCompany(e: React.FormEvent) {
    e.preventDefault();
    if (!editingCompanyId || !companyName.trim()) return;

    setIsUpdatingCompany(true);

    try {
      // First, upload audio file if provided
      let audioPath: string | undefined = undefined;
      if (companyAudio) {
        const uploadData = await apiUploadFile("/upload-audio", companyAudio) as { audio_path?: string };
        audioPath = uploadData.audio_path;
      }

      // Then update the company with the audio path
      const updatedCompany = await apiPut<Company>(
        `/companies/${editingCompanyId}`,
        {
          name: companyName.trim(),
          website: companyWebsite.trim() || undefined,
          audio_path: audioPath,
        }
      );

      // Replace company in list
      setCompanies((prev) =>
        prev.map((c) => (c.id === editingCompanyId ? updatedCompany : c))
      );

      // Keep selection
      if (selectedCompanyId === editingCompanyId) {
        setSelectedCompanyId(editingCompanyId);
      }

      // Clear form and close dialog
      setCompanyName("");
      setCompanyWebsite("");
      setCompanyAudio(null);
      setCompanyDocs(null);
      setEditingCompanyId(null);
      setShowCompanyDialog(false);
    } catch (error: unknown) {
      console.error("Error updating company:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to update company. Please try again.";
      alert(errorMsg);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsUpdatingCompany(false);
    }
  }

  // Delete company
  async function handleDeleteCompany() {
    if (!deletingCompanyId) return;

    setIsDeletingCompany(true);

    try {
      await apiDelete(`/companies/${deletingCompanyId}`);

      // Remove company from list
      setCompanies((prev) => prev.filter((c) => c.id !== deletingCompanyId));

      // Clear selection if it was selected
      if (selectedCompanyId === deletingCompanyId) {
        setSelectedCompanyId(null);
      }

      // Close confirmation dialog
      setDeletingCompanyId(null);
    } catch (error: unknown) {
      console.error("Error deleting company:", error);
      const errorMsg = error instanceof Error ? error.message : "Failed to delete company. Please try again.";
      alert(errorMsg);
      if (error instanceof Error && error.message.includes("Authentication required")) {
        logout();
      }
    } finally {
      setIsDeletingCompany(false);
    }
  }

  // Close menus when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as HTMLElement;
      if (!target.closest(`.${styles.menuContainer}`)) {
        setShowCompanyMenu(false);
        setOpenProgramMenuId(null);
        setOpenCompanyMenuId(null);
      }
    }
    if (showCompanyMenu || openProgramMenuId !== null || openCompanyMenuId !== null) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showCompanyMenu, openProgramMenuId, openCompanyMenuId]);

  return (
    <div className={styles.container}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <h2 className={styles.sidebarTitle}>Projects</h2>
        <button
          className={`${styles.sidebarItem} ${
            activeTab === "funding" ? styles.activeSidebarItem : ""
          }`}
          onClick={() => {
            setActiveTab("funding");
            setSelectedProgramId(null);
            setSelectedCompanyId(null);
            setCompanies([]); // Clear companies when switching tabs
          }}
        >
          Funding Program
        </button>
        <button
          className={`${styles.sidebarItem} ${
            activeTab === "without" ? styles.activeSidebarItem : ""
          }`}
          onClick={() => {
            setActiveTab("without");
            setSelectedProgramId(null);
            setSelectedCompanyId(null);
            setCompanies([]); // Clear companies when switching tabs
          }}
        >
          Without Funding Program
        </button>
        <button
          className={`${styles.sidebarItem} ${
            activeTab === "collab" ? styles.activeSidebarItem : ""
          }`}
          onClick={() => {
            setActiveTab("collab");
            setSelectedProgramId(null);
            setSelectedCompanyId(null);
            setCompanies([]); // Clear companies when switching tabs
          }}
        >
          Collaboration
        </button>
      </aside>

      {/* Main content */}
      <div className={styles.content}>
        {/* Funding tab */}
        {activeTab === "funding" && (
          <>
            <header className={styles.header}>
              <div className={styles.headerContent}>
                <div>
                  <h1 className={styles.title}>Innovo Funding Workspace</h1>
                  <p className={styles.subtitle}>
                    Select a funding program, choose a company, then generate
                    documents.
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  className={styles.logoutButton}
                  title="Logout"
                >
                  Logout
                </button>
              </div>
            </header>

            <div className={styles.layout}>
              {/* Funding program section */}
              <section className={styles.programColumn}>
                <div className={styles.programHeader}>
                  <h2 className={styles.programTitle}>Funding Programs</h2>
                  <button
                    onClick={() => setShowProgramDialog(true)}
                    className={styles.newProgramButton}
                  >
                    + New Funding Program
                  </button>
                </div>
                {/* Search input for funding programs */}
                <div style={{ padding: "0.5rem", marginBottom: "0.5rem" }}>
                  <input
                    type="text"
                    placeholder="Search programs..."
                    value={programSearchTerm}
                    onChange={(e) => setProgramSearchTerm(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "0.5rem",
                      border: "1px solid var(--brand-border)",
                      borderRadius: "4px",
                      fontSize: "0.9rem",
                    }}
                  />
                </div>
                <div className={styles.programList}>
                  {isLoadingPrograms ? (
                    <div>Loading programs...</div>
                  ) : filteredPrograms.length === 0 ? (
                    <div>
                      {programs.length === 0
                        ? "No funding programs found."
                        : `No programs match "${programSearchTerm}"`}
                    </div>
                  ) : (
                    filteredPrograms.map((p) => (
                      <div
                        key={p.id}
                        className={`${styles.programItem} ${
                          selectedProgramId === p.id
                            ? styles.programItemActive
                            : ""
                        }`}
                      >
                        <div
                          onClick={() => {
                            const newProgramId = selectedProgramId === p.id ? null : p.id;
                            setSelectedProgramId(newProgramId);
                            // Companies will be cleared and fetched via useEffect
                          }}
                          style={{ flex: 1, cursor: "pointer" }}
                        >
                          <div className={styles.programName}>{p.title}</div>
                          {p.website && (
                            <div className={styles.programWebsite}>
                              {p.website}
                            </div>
                          )}
                          {p.last_scraped_at && (
                            <div style={{ fontSize: "0.75rem", color: "#666", marginTop: "0.25rem" }}>
                              Last scraped: {new Date(p.last_scraped_at).toLocaleString()}
                            </div>
                          )}
                        </div>
                        <div className={styles.menuContainer}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenProgramMenuId(openProgramMenuId === p.id ? null : p.id);
                            }}
                            className={styles.menuButton}
                          >
                            ⋮
                          </button>
                          {openProgramMenuId === p.id && (
                            <div className={styles.menuDropdown}>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditingProgramId(p.id);
                                  setProgramTitle(p.title);
                                  setProgramWebsite(p.website || "");
                                  // Determine template source from existing program
                                  if (p.template_source && p.template_ref) {
                                    setProgramTemplateSource(p.template_source);
                                    setProgramTemplate(p.template_ref);
                                  } else if (p.template_name) {
                                    // Legacy: assume system template if only template_name exists
                                    setProgramTemplateSource("system");
                                    setProgramTemplate(p.template_name);
                                  } else {
                                    setProgramTemplateSource("");
                                    setProgramTemplate("");
                                  }
                                  setShowProgramDialog(true);
                                  setOpenProgramMenuId(null);
                                }}
                                className={styles.menuItem}
                              >
                                Edit
                              </button>
                              {p.website && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRefreshProgram(p.id);
                                  }}
                                  className={styles.menuItem}
                                  disabled={scrapingProgramId === p.id}
                                >
                                  {scrapingProgramId === p.id ? "Refreshing..." : "Refresh Data"}
                                </button>
                              )}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeletingProgramId(p.id);
                                  setOpenProgramMenuId(null);
                                }}
                                className={styles.menuItem}
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              {/* Companies section — shown only if a program is selected */}
              {selectedProgramId && (
                <section className={styles.companyColumn}>
                  <div className={styles.companyHeader}>
                    <h2 className={styles.companyTitle}>Companies</h2>
                    <div className={styles.menuContainer}>
                      <button
                        onClick={() => setShowCompanyMenu(!showCompanyMenu)}
                        className={styles.menuButton}
                      >
                        ⋮
                      </button>
                      {showCompanyMenu && (
                        <div className={styles.menuDropdown}>
                          <button
                            onClick={() => {
                              setShowCompanyDialog(true);
                              setShowCompanyMenu(false);
                            }}
                            className={styles.menuItem}
                          >
                            Add New Company
                          </button>
                          <button
                            onClick={() => {
                              setShowImportDialog(true);
                              setShowCompanyMenu(false);
                            }}
                            className={styles.menuItem}
                          >
                            Import Existing Company
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                  {/* Search input for companies */}
                  <div style={{ padding: "0.5rem", marginBottom: "0.5rem" }}>
                    <input
                      type="text"
                      placeholder="Search companies..."
                      value={companySearchTerm}
                      onChange={(e) => setCompanySearchTerm(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "0.5rem",
                        border: "1px solid var(--brand-border)",
                        borderRadius: "4px",
                        fontSize: "0.9rem",
                      }}
                    />
                  </div>
                  <div className={styles.companyList}>
                    {isLoadingCompanies ? (
                      <div>Loading companies...</div>
                    ) : filteredCompanies.length === 0 ? (
                      <div>
                        {companies.length === 0
                          ? "No companies found for this funding program."
                          : `No companies match "${companySearchTerm}"`}
                      </div>
                    ) : (
                      filteredCompanies.map((c) => (
                        <div
                          key={c.id}
                          className={`${styles.companyItem} ${
                            selectedCompanyId === c.id
                              ? styles.companyItemActive
                              : ""
                          }`}
                        >
                          <div
                            onClick={() => setSelectedCompanyId(c.id)}
                            style={{ flex: 1, cursor: "pointer" }}
                          >
                            <div className={styles.companyName}>{c.name}</div>
                            {c.website && (
                              <div className={styles.companyWebsite}>
                                {c.website}
                              </div>
                            )}
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            {c.audio_path && (
                              <span className={styles.audioIcon}>
                                🎙 {c.audio_path}
                              </span>
                            )}
                            <div className={styles.menuContainer}>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenCompanyMenuId(openCompanyMenuId === c.id ? null : c.id);
                                }}
                                className={styles.menuButton}
                              >
                                ⋮
                              </button>
                              {openCompanyMenuId === c.id && (
                                <div className={styles.menuDropdown}>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setEditingCompanyId(c.id);
                                      setCompanyName(c.name);
                                      setCompanyWebsite(c.website || "");
                                      setShowCompanyDialog(true);
                                      setOpenCompanyMenuId(null);
                                    }}
                                    className={styles.menuItem}
                                  >
                                    Edit
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setDeletingCompanyId(c.id);
                                      setOpenCompanyMenuId(null);
                                    }}
                                    className={styles.menuItem}
                                  >
                                    Delete
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </section>
              )}

              {/* Documents section — only shown when both program and company are selected */}
              {selectedProgramId && selectedCompanyId && (
                <section className={styles.docColumn}>
                  <h2 className={styles.docsTitle}>Documents</h2>
                  <p className={styles.docsHint}>Choose which document to open.</p>
                  <button
                    onClick={() => handleOpenEditor("vorhaben")}
                    className={styles.docButton}
                  >
                    Vorhabensbeschreibung
                  </button>
                  <button
                    onClick={() => handleOpenEditor("vorkalkulation")}
                    className={styles.docButtonAlt}
                  >
                    Vorkalkulation
                  </button>
                </section>
              )}
            </div>
          </>
        )}

        {/* Without Funding Program tab */}
        {activeTab === "without" && (
          <>
            <header className={styles.header}>
              <div className={styles.headerContent}>
                <div>
                  <h1 className={styles.title}>Add Company Without Program</h1>
                  <p className={styles.subtitle}>
                    Create or select a company without linking to any funding program.
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  className={styles.logoutButton}
                  title="Logout"
                >
                  Logout
                </button>
              </div>
            </header>

            <div className={styles.layout}>
              {/* Companies (always shown here) */}
              <section className={styles.companyColumn}>
                  <div className={styles.companyHeader}>
                    <h2 className={styles.companyTitle}>Companies</h2>
                    <div className={styles.menuContainer}>
                      <button
                        onClick={() => setShowCompanyMenu(!showCompanyMenu)}
                        className={styles.menuButton}
                      >
                        ⋮
                      </button>
                      {showCompanyMenu && (
                        <div className={styles.menuDropdown}>
                          <button
                            onClick={() => {
                              setShowCompanyDialog(true);
                              setShowCompanyMenu(false);
                            }}
                            className={styles.menuItem}
                          >
                            Add New Company
                          </button>
                          <button
                            onClick={() => {
                              setShowImportDialog(true);
                              setShowCompanyMenu(false);
                            }}
                            className={styles.menuItem}
                          >
                            Import Existing Company
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                <div className={styles.companyList}>
                  {companies.map((c) => (
                    <div
                      key={c.id}
                      className={`${styles.companyItem} ${
                        selectedCompanyId === c.id
                          ? styles.companyItemActive
                          : ""
                      }`}
                      onClick={() => setSelectedCompanyId(c.id)}
                    >
                      <div>
                        <div className={styles.companyName}>{c.name}</div>
                        {c.website && (
                          <div className={styles.companyWebsite}>{c.website}</div>
                        )}
                      </div>
                      {c.audio_path && (
                        <span className={styles.audioIcon}>
                          🎙 {c.audio_path}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              {/* Documents appear only after selecting a company */}
              {selectedCompanyId && (
                <section className={styles.docColumn}>
                  <h2 className={styles.docsTitle}>Documents</h2>
                  <p className={styles.docsHint}>
                    Choose which document to open.
                  </p>
                  <button
                    onClick={() => handleOpenEditor("vorhaben")}
                    className={styles.docButton}
                  >
                    Vorhabensbeschreibung
                  </button>
                  <button
                    onClick={() => handleOpenEditor("vorkalkulation")}
                    className={styles.docButtonAlt}
                  >
                    Vorkalkulation
                  </button>
                </section>
              )}
            </div>
          </>
        )}

        {/* Collaboration tab */}
        {activeTab === "collab" && (
          <>
            <header className={styles.header}>
              <div className={styles.headerContent}>
                <div>
                  <h1 className={styles.title}>Collaborate</h1>
                  <p className={styles.subtitle}>
                    Collaboration features (coming soon).
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  className={styles.logoutButton}
                  title="Logout"
                >
                  Logout
                </button>
              </div>
            </header>
            <div className={styles.layout}>
              <p className={styles.collabPlaceholder}>
                Collaboration projects will be added in a future update.
              </p>
            </div>
          </>
        )}
      </div>

      {/* Program dialog */}
      {showProgramDialog && (
        <div
          className={styles.dialogOverlay}
          onClick={() => {
            setShowProgramDialog(false);
            setEditingProgramId(null);
            setProgramTitle("");
            setProgramWebsite("");
            setProgramTemplate("");
          }}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className={styles.dialogTitle}>
              {editingProgramId ? "Edit Funding Program" : "New Funding Program"}
            </h3>
            <form onSubmit={editingProgramId ? handleUpdateProgram : handleCreateProgram}>
              <label className={styles.formLabel}>
                Title <span className={styles.required}>*</span>
              </label>
              <input
                value={programTitle}
                onChange={(e) => setProgramTitle(e.target.value)}
                required
                className={styles.formInput}
              />
              <label className={styles.formLabel}>Website (optional)</label>
              <input
                value={programWebsite}
                onChange={(e) => setProgramWebsite(e.target.value)}
                placeholder="https://…"
                className={styles.formInput}
              />
              <label className={styles.formLabel}>Document Template (optional)</label>
              <div style={{ marginBottom: "0.5rem" }}>
                <select
                  value={programTemplateSource}
                  onChange={(e) => {
                    setProgramTemplateSource(e.target.value as "system" | "user" | "");
                    setProgramTemplate(""); // Reset template selection when source changes
                  }}
                  className={styles.formInput}
                  style={{ marginBottom: "0.5rem" }}
                >
                  <option value="">No template</option>
                  <option value="system">System Template</option>
                  <option value="user">User Template</option>
                </select>
              </div>
              {programTemplateSource && (
                <select
                  value={programTemplate}
                  onChange={(e) => setProgramTemplate(e.target.value)}
                  className={styles.formInput}
                >
                  <option value="">Select a template...</option>
                  {programTemplateSource === "system" && availableTemplates.system.length > 0 ? (
                    availableTemplates.system.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))
                  ) : programTemplateSource === "system" ? (
                    <option value="" disabled>No system templates available</option>
                  ) : null}
                  {programTemplateSource === "user" && availableTemplates.user.length > 0 ? (
                    availableTemplates.user.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} {t.description ? `- ${t.description}` : ""}
                      </option>
                    ))
                  ) : programTemplateSource === "user" ? (
                    <option value="" disabled>No user templates available</option>
                  ) : null}
                </select>
              )}
              <div style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "#6b7280" }}>
                <a
                  href="/templates/new"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate("/templates/new");
                  }}
                  style={{ color: "var(--brand-primary, #2563eb)", textDecoration: "underline" }}
                >
                  Create new template
                </a>
              </div>
              <div className={styles.dialogActions}>
                <button
                  type="button"
                  onClick={() => {
                    setShowProgramDialog(false);
                    setEditingProgramId(null);
                    setProgramTitle("");
                    setProgramWebsite("");
                    setProgramTemplate("");
                  }}
                  className={styles.cancelButton}
                  disabled={isCreatingProgram || isUpdatingProgram}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.createButton}
                  disabled={isCreatingProgram || isUpdatingProgram}
                >
                  {isCreatingProgram
                    ? "Creating..."
                    : isUpdatingProgram
                    ? "Updating..."
                    : editingProgramId
                    ? "Update"
                    : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Program Confirmation */}
      {deletingProgramId && (
        <div
          className={styles.dialogOverlay}
          onClick={() => setDeletingProgramId(null)}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className={styles.dialogTitle}>Delete Funding Program</h3>
            <p>Are you sure you want to delete this funding program? This action cannot be undone.</p>
            <div className={styles.dialogActions}>
              <button
                type="button"
                onClick={() => setDeletingProgramId(null)}
                className={styles.cancelButton}
                disabled={isDeletingProgram}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteProgram}
                className={styles.createButton}
                disabled={isDeletingProgram}
                style={{ backgroundColor: "#b32020" }}
              >
                {isDeletingProgram ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Company dialog */}
      {showCompanyDialog && (
        <div
          className={styles.dialogOverlay}
          onClick={() => {
            setShowCompanyDialog(false);
            setEditingCompanyId(null);
            setCompanyName("");
            setCompanyWebsite("");
            setCompanyAudio(null);
            setCompanyDocs(null);
          }}
        >
          <div
            className={styles.dialogBoxLarge}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className={styles.dialogTitle}>
              {editingCompanyId ? "Edit Company" : "New Company"}
            </h3>
            <form onSubmit={editingCompanyId ? handleUpdateCompany : handleCreateCompany}>
              <label className={styles.formLabel}>
                Company Name <span className={styles.required}>*</span>
              </label>
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                required
                className={styles.formInput}
                disabled={isCreatingCompany}
              />
              <label className={styles.formLabel}>Website (optional)</label>
              <input
                value={companyWebsite}
                onChange={(e) => setCompanyWebsite(e.target.value)}
                placeholder="https://…"
                className={styles.formInput}
                disabled={isCreatingCompany}
              />
              <label className={styles.formLabel}>Meeting Audio</label>
              <input
                type="file"
                accept="audio/*"
                onChange={(e) =>
                  setCompanyAudio(e.target.files?.[0] ?? null)
                }
                className={styles.formFile}
                disabled={isCreatingCompany}
              />
              <label className={styles.formLabel}>Other Documents</label>
              <input
                type="file"
                multiple
                onChange={(e) => setCompanyDocs(e.target.files)}
                className={styles.formFile}
                disabled={isCreatingCompany}
              />
              <div className={styles.dialogActions}>
                <button
                  type="button"
                  onClick={() => {
                    setShowCompanyDialog(false);
                    setEditingCompanyId(null);
                    setCompanyName("");
                    setCompanyWebsite("");
                    setCompanyAudio(null);
                    setCompanyDocs(null);
                  }}
                  className={styles.cancelButton}
                  disabled={isCreatingCompany || isUpdatingCompany}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.createButton}
                  disabled={isCreatingCompany || isUpdatingCompany}
                >
                  {isCreatingCompany
                    ? "Creating..."
                    : isUpdatingCompany
                    ? "Updating..."
                    : editingCompanyId
                    ? "Update"
                    : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Company Confirmation */}
      {deletingCompanyId && (
        <div
          className={styles.dialogOverlay}
          onClick={() => setDeletingCompanyId(null)}
        >
          <div
            className={styles.dialogBox}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className={styles.dialogTitle}>Delete Company</h3>
            <p>Are you sure you want to delete this company? This action cannot be undone.</p>
            <div className={styles.dialogActions}>
              <button
                type="button"
                onClick={() => setDeletingCompanyId(null)}
                className={styles.cancelButton}
                disabled={isDeletingCompany}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteCompany}
                className={styles.createButton}
                disabled={isDeletingCompany}
                style={{ backgroundColor: "#b32020" }}
              >
                {isDeletingCompany ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import Company dialog */}
      {showImportDialog && (
        <div
          className={styles.dialogOverlay}
          onClick={() => setShowImportDialog(false)}
        >
          <div
            className={styles.dialogBoxLarge}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className={styles.dialogTitle}>Import Existing Company</h3>
            {isLoadingAllCompanies ? (
              <div>Loading companies...</div>
            ) : allCompanies.length === 0 ? (
              <div>No companies available to import.</div>
            ) : (
              <div className={styles.importList}>
                {allCompanies.map((company) => {
                  const isAlreadyLinked = companies.some(
                    (c) => c.id === company.id
                  );
                  return (
                    <div
                      key={company.id}
                      className={`${styles.importItem} ${
                        isAlreadyLinked ? styles.importItemDisabled : ""
                      }`}
                    >
                      <div>
                        <div className={styles.companyName}>{company.name}</div>
                        {company.website && (
                          <div className={styles.companyWebsite}>
                            {company.website}
                          </div>
                        )}
                      </div>
                      {isAlreadyLinked ? (
                        <span className={styles.alreadyLinked}>Linked</span>
                      ) : (
                        <button
                          onClick={() => handleImportCompany(company.id)}
                          className={styles.importButton}
                          disabled={isImportingCompany}
                        >
                          {isImportingCompany ? "Importing..." : "Import"}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            <div className={styles.dialogActions}>
              <button
                type="button"
                onClick={() => setShowImportDialog(false)}
                className={styles.cancelButton}
                disabled={isImportingCompany}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
