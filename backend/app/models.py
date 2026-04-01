from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Table, UniqueConstraint, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class User(Base):
    __tablename__ = "users"

    email = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Password reset fields - stored as hashed token for security
    reset_token_hash = Column(String, nullable=True)  # Hashed reset token
    reset_token_expiry = Column(DateTime(timezone=True), nullable=True)  # Token expiration time
    # Phase 2: admin flag for funding program management gate
    is_admin = Column(Boolean, nullable=False, default=False)

    # Relationships to user-owned resources
    funding_programs = relationship("FundingProgram", back_populates="user")
    companies = relationship("Company", back_populates="user")

class FundingProgram(Base):
    __tablename__ = "funding_programs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    website = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_email = Column(String, ForeignKey("users.email"), nullable=False, index=True)

    # Relationship to user (owner)
    user = relationship("User", back_populates="funding_programs")

    # Many-to-many relationship with companies
    companies = relationship(
        "Company",
        secondary="funding_program_companies",
        back_populates="funding_programs"
    )

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    website_text = Column(String, nullable=True)  # Crawled website content (legacy, kept for backward compatibility)
    transcript_text = Column(String, nullable=True)  # Audio transcript (legacy, kept for backward compatibility)
    # New raw content fields
    website_raw_text = Column(Text, nullable=True)  # Raw extracted website text
    website_clean_text = Column(Text, nullable=True)  # Cleaned website text (navigation/boilerplate removed)
    transcript_raw = Column(Text, nullable=True)  # Raw transcript from Whisper
    transcript_clean = Column(Text, nullable=True)  # Cleaned transcript (filler words removed, normalized)
    processing_status = Column(String, nullable=True, server_default="pending")  # "pending", "processing", "done", "failed"
    processing_error = Column(String, nullable=True)  # Error message if processing failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    user_email = Column(String, ForeignKey("users.email"), nullable=False, index=True)

    # Structured company profile (Phase 2A: Extract → Store → Reference)
    company_profile = Column(JSONB, nullable=True)  # Structured extracted company information
    extraction_status = Column(String, nullable=True)  # "pending", "extracted", "failed"
    extracted_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp when extraction completed

    # Relationship to user (owner)
    user = relationship("User", back_populates="companies")

    # Many-to-many relationship with funding programs
    funding_programs = relationship(
        "FundingProgram",
        secondary="funding_program_companies",
        back_populates="companies"
    )

# Join table for many-to-many relationship
funding_program_companies = Table(
    "funding_program_companies",
    Base.metadata,
    Column("funding_program_id", Integer, ForeignKey("funding_programs.id"), primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), primary_key=True),
    UniqueConstraint("funding_program_id", "company_id", name="uq_funding_program_company")
)

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)  # "vorhabensbeschreibung", "vorkalkulation"
    content_json = Column(JSONB, nullable=False)  # Stores sections array as JSON
    chat_history = Column(JSONB, nullable=True)  # Stores chat messages as JSON array
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Phase 2.6: Headings confirmation flag
    # Use Integer for SQLite compatibility (0 = False, 1 = True), works with PostgreSQL too
    headings_confirmed = Column(Integer, nullable=False, server_default="0")

    # Funding program association (nullable for legacy documents)
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id"), nullable=True, index=True)

    # Template association
    # template_id: UUID FK to user_templates (for user-defined templates)
    # template_name: String for system templates (e.g., "wtt_v1")
    # If both are None, use default system template
    template_id = Column(UUID(as_uuid=True), ForeignKey("user_templates.id"), nullable=True, index=True)
    template_name = Column(String, nullable=True)  # System template name (e.g., "wtt_v1")

    # Optional title to distinguish multiple documents per (company, funding_program, type)
    title = Column(String, nullable=True)

    # v2: nullable FK to project; NULL = pre-v2 document (backward-compat fallback applies)
    project_id = Column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships (no unique constraint - multiple docs per company+program+type allowed)
    company = relationship("Company", backref="documents")
    funding_program = relationship("FundingProgram", backref="documents")
    template = relationship("UserTemplate", backref="documents")  # For user templates

class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    content_hash = Column(Text, unique=True, nullable=False, index=True)
    file_type = Column(Text, nullable=True)  # e.g., "audio", "pdf", "docx"
    storage_path = Column(Text, nullable=False)  # Path in Supabase Storage
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Phase 2: Raw Processing Cache Tables

class AudioTranscriptCache(Base):
    """
    Cache for audio transcription results.
    Keyed by file content_hash to ensure same audio file is transcribed only once.
    """
    __tablename__ = "audio_transcript_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_content_hash = Column(Text, unique=True, nullable=False, index=True)  # References File.content_hash
    transcript_text = Column(Text, nullable=False)  # Cached transcript from Whisper
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # When transcription ran
class WebsiteTextCache(Base):
    """
    Cache for website crawling results.
    Keyed by normalized URL hash to ensure same website is crawled only once.
    """
    __tablename__ = "website_text_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    url_hash = Column(Text, unique=True, nullable=False, index=True)  # SHA256 hash of normalized URL
    normalized_url = Column(Text, nullable=False)  # Normalized URL for reference
    website_text = Column(Text, nullable=False)  # Cached crawled text
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # When crawl ran
class DocumentTextCache(Base):
    """
    Cache for PDF/DOCX document text extraction results.
    Keyed by file content_hash to ensure same document is extracted only once.
    """
    __tablename__ = "document_text_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_content_hash = Column(Text, unique=True, nullable=False, index=True)  # References File.content_hash
    extracted_text = Column(Text, nullable=False)  # Cached extracted text
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # When extraction ran

# Phase 2.5: User Template Model
class UserTemplate(Base):
    """
    User-defined document templates stored in database.
    """
    __tablename__ = "user_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    template_structure = Column(JSONB, nullable=False)  # Contains "sections" key
    user_email = Column(String, ForeignKey("users.email"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to user
    user = relationship("User", backref="user_templates")

# Phase 4: Funding Program Document Model
class FundingProgramDocument(Base):
    """
    Documents uploaded for funding programs (PDFs, text files, etc.).
    Links funding programs to files with category organization.
    """
    __tablename__ = "funding_program_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True)
    category = Column(String, nullable=False)  # e.g., "guidelines", "examples", "forms"
    original_filename = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.email"), nullable=False)

    # Composite index for efficient category filtering
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    # Relationships
    funding_program = relationship("FundingProgram", backref="funding_program_documents")
    file = relationship("File", backref="funding_program_documents")
    uploader = relationship("User", backref="uploaded_documents")

class CompanyDocument(Base):
    """
    Documents uploaded for companies (PDFs, DOCX, etc.).
    Links companies to files. Separate from funding program documents.
    """
    __tablename__ = "company_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.email"), nullable=False)

    # Composite index for efficient queries
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    # Relationships
    company = relationship("Company", backref="company_documents")
    file = relationship("File", backref="company_documents")
    uploader = relationship("User", backref="uploaded_company_documents")

class FundingProgramGuidelinesSummary(Base):
    """
    Structured rules extracted from funding program guideline documents.
    One summary per funding program, regenerated when guideline files change.
    """
    __tablename__ = "funding_program_guidelines_summary"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id"), nullable=False, unique=True, index=True)
    rules_json = Column(JSONB, nullable=False)  # Structured rules extracted from guidelines
    source_file_hash = Column(Text, nullable=False)  # Combined hash of all guideline files
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    funding_program = relationship("FundingProgram", backref="guidelines_summary")

class AlteVorhabensbeschreibungDocument(Base):
    """
    Historical Vorhabensbeschreibung documents for writing style extraction.
    System-level module, not linked to funding programs or companies.
    """
    __tablename__ = "alte_vorhabensbeschreibung_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.email"), nullable=False)

    # Relationships
    file = relationship("File", backref="alte_vorhabensbeschreibung_documents")
    uploader = relationship("User", backref="uploaded_alte_vorhabensbeschreibung_documents")

class AlteVorhabensbeschreibungStyleProfile(Base):
    """
    System-level writing style profile extracted from historical documents.
    Only ONE active profile should exist at a time.
    """
    __tablename__ = "alte_vorhabensbeschreibung_style_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    combined_hash = Column(Text, unique=True, nullable=False, index=True)  # SHA256 hash of all document content hashes
    style_summary_json = Column(JSONB, nullable=False)  # Extracted writing style patterns
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Project(Base):
    """
    v2 Project entity — the central coordination layer for document generation.
    Binds a user, company, funding program, and topic into a single workspace.
    """
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, ForeignKey("users.email", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id", ondelete="SET NULL"), nullable=True)
    # Phase 2: free-text company name for projects created without a pre-existing Company record
    company_name = Column(Text, nullable=True)
    # Phase 2: optional JSON overrides for template structure at project level
    template_overrides_json = Column(JSONB, nullable=True)
    topic = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="assembling")  # assembling | ready | generating | complete
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    context = relationship("ProjectContext", back_populates="project", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_projects_user_email", "user_email"),
        Index("ix_projects_company_id", "company_id"),
        Index("ix_projects_funding_program_id", "funding_program_id"),
        Index("ix_projects_created_at", "created_at"),
    )


class ProjectContext(Base):
    """
    Pre-assembled context snapshot for a project.
    Created once by the context assembler; regenerated when inputs change.
    All JSON fields are nullable — assembly may be partial.
    """
    __tablename__ = "project_contexts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_profile_json = Column(JSONB, nullable=True)
    funding_rules_json = Column(JSONB, nullable=True)
    domain_research_json = Column(JSONB, nullable=True)
    retrieved_examples_json = Column(JSONB, nullable=True)
    style_profile_json = Column(JSONB, nullable=True)
    website_text_preview = Column(Text, nullable=True)  # plain text, not JSON
    context_hash = Column(String, nullable=True)
    # Phase 2: assembly tracking fields
    completeness_score = Column(Integer, nullable=True)
    company_discovery_status = Column(String, nullable=True)  # "found" | "partial" | "not_found"
    assembly_progress_json = Column(JSONB, nullable=True)  # per-stage progress map
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project = relationship("Project", back_populates="context")


class ProjectChatMessage(Base):
    """
    A single chat turn in the project-scoped chatbot conversation.
    Persisted per project; role is "user" or "assistant".
    """
    __tablename__ = "project_chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# Phase 4: Knowledge Base

class FundingProgramSource(Base):
    """
    A web URL that is periodically scraped and indexed into the knowledge base
    as 'guideline' category chunks.  One source can produce one KnowledgeBaseDocument
    (and its associated chunks).  The content_hash field enables change detection so
    unchanged pages are not re-indexed on every scrape run.
    """
    __tablename__ = "funding_program_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    funding_program_id = Column(
        Integer, ForeignKey("funding_programs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    url = Column(String, nullable=False)
    label = Column(String, nullable=True)                         # optional human-readable label
    status = Column(String, nullable=False, default="pending")    # pending | scraping | done | failed
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String, nullable=True)                  # SHA-256 of scraped text
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    funding_program = relationship("FundingProgram", backref="sources")


class KnowledgeBaseDocument(Base):
    """
    Document registered in the knowledge base.
    Can originate from two sources:
      1. Admin file upload  — file_id is set, source_id is NULL
      2. Web scrape via FundingProgramSource — source_id is set, file_id is NULL
    Chunks and embeddings are derived from this document via the indexing pipeline.
    """
    __tablename__ = "knowledge_base_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)   # "example" | "guideline" | "domain" | "other"
    program_tag = Column(String, nullable=True, index=True) # optional: used to scope retrieval per program
    # Nullable — NULL for scrape-sourced docs; set for upload-sourced docs
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), nullable=True)
    # Nullable — set only for web-scrape sourced docs; NULL for uploaded docs
    source_id = Column(UUID(as_uuid=True), ForeignKey("funding_program_sources.id", ondelete="CASCADE"), nullable=True, index=True)
    uploaded_by = Column(String, ForeignKey("users.email", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    file = relationship("File", backref="knowledge_base_documents")
    source = relationship("FundingProgramSource", backref="kb_document")
    chunks = relationship("KnowledgeBaseChunk", back_populates="document",
                          cascade="all, delete-orphan")


class KnowledgeBaseChunk(Base):
    """
    A text chunk derived from a KnowledgeBaseDocument.
    The embedding column holds a 1536-dimensional pgvector vector produced by
    text-embedding-3-small. Similarity search uses cosine distance (<=>).
    """
    __tablename__ = "knowledge_base_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True),
                         ForeignKey("knowledge_base_documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)  # nullable until indexing completes
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("KnowledgeBaseDocument", back_populates="chunks")
