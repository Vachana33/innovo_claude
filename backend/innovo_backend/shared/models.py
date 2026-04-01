from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Table, UniqueConstraint, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from innovo_backend.shared.database import Base
import uuid


class User(Base):
    __tablename__ = "users"

    email = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reset_token_hash = Column(String, nullable=True)
    reset_token_expiry = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)

    funding_programs = relationship("FundingProgram", back_populates="user")
    companies = relationship("Company", back_populates="user")


class FundingProgram(Base):
    __tablename__ = "funding_programs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    website = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_email = Column(String, ForeignKey("users.email"), nullable=False, index=True)

    user = relationship("User", back_populates="funding_programs")
    companies = relationship(
        "Company",
        secondary="funding_program_companies",
        back_populates="funding_programs",
    )


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    website_text = Column(String, nullable=True)
    transcript_text = Column(String, nullable=True)
    website_raw_text = Column(Text, nullable=True)
    website_clean_text = Column(Text, nullable=True)
    transcript_raw = Column(Text, nullable=True)
    transcript_clean = Column(Text, nullable=True)
    processing_status = Column(String, nullable=True, server_default="pending")
    processing_error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    user_email = Column(String, ForeignKey("users.email"), nullable=False, index=True)

    company_profile = Column(JSONB, nullable=True)
    extraction_status = Column(String, nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="companies")
    funding_programs = relationship(
        "FundingProgram",
        secondary="funding_program_companies",
        back_populates="companies",
    )


funding_program_companies = Table(
    "funding_program_companies",
    Base.metadata,
    Column("funding_program_id", Integer, ForeignKey("funding_programs.id"), primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), primary_key=True),
    UniqueConstraint("funding_program_id", "company_id", name="uq_funding_program_company"),
)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    content_json = Column(JSONB, nullable=False)
    chat_history = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    headings_confirmed = Column(Integer, nullable=False, server_default="0")
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id"), nullable=True, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("user_templates.id"), nullable=True, index=True)
    template_name = Column(String, nullable=True)
    title = Column(String, nullable=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    company = relationship("Company", backref="documents")
    funding_program = relationship("FundingProgram", backref="documents")
    template = relationship("UserTemplate", backref="documents")


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    content_hash = Column(Text, unique=True, nullable=False, index=True)
    file_type = Column(Text, nullable=True)
    storage_path = Column(Text, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AudioTranscriptCache(Base):
    __tablename__ = "audio_transcript_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_content_hash = Column(Text, unique=True, nullable=False, index=True)
    transcript_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WebsiteTextCache(Base):
    __tablename__ = "website_text_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    url_hash = Column(Text, unique=True, nullable=False, index=True)
    normalized_url = Column(Text, nullable=False)
    website_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentTextCache(Base):
    __tablename__ = "document_text_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_content_hash = Column(Text, unique=True, nullable=False, index=True)
    extracted_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserTemplate(Base):
    __tablename__ = "user_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    template_structure = Column(JSONB, nullable=False)
    user_email = Column(String, ForeignKey("users.email"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="user_templates")


class FundingProgramDocument(Base):
    __tablename__ = "funding_program_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.email"), nullable=False)

    __table_args__ = ({"sqlite_autoincrement": True},)

    funding_program = relationship("FundingProgram", backref="funding_program_documents")
    file = relationship("File", backref="funding_program_documents")
    uploader = relationship("User", backref="uploaded_documents")


class CompanyDocument(Base):
    __tablename__ = "company_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.email"), nullable=False)

    __table_args__ = ({"sqlite_autoincrement": True},)

    company = relationship("Company", backref="company_documents")
    file = relationship("File", backref="company_documents")
    uploader = relationship("User", backref="uploaded_company_documents")


class FundingProgramGuidelinesSummary(Base):
    __tablename__ = "funding_program_guidelines_summary"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id"), nullable=False, unique=True, index=True)
    rules_json = Column(JSONB, nullable=False)
    source_file_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    funding_program = relationship("FundingProgram", backref="guidelines_summary")


class AlteVorhabensbeschreibungDocument(Base):
    __tablename__ = "alte_vorhabensbeschreibung_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.email"), nullable=False)

    file = relationship("File", backref="alte_vorhabensbeschreibung_documents")
    uploader = relationship("User", backref="uploaded_alte_vorhabensbeschreibung_documents")


class AlteVorhabensbeschreibungStyleProfile(Base):
    __tablename__ = "alte_vorhabensbeschreibung_style_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    combined_hash = Column(Text, unique=True, nullable=False, index=True)
    style_summary_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, ForeignKey("users.email", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    funding_program_id = Column(Integer, ForeignKey("funding_programs.id", ondelete="SET NULL"), nullable=True)
    company_name = Column(Text, nullable=True)
    template_overrides_json = Column(JSONB, nullable=True)
    topic = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="assembling")
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
    __tablename__ = "project_contexts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_profile_json = Column(JSONB, nullable=True)
    funding_rules_json = Column(JSONB, nullable=True)
    domain_research_json = Column(JSONB, nullable=True)
    retrieved_examples_json = Column(JSONB, nullable=True)
    style_profile_json = Column(JSONB, nullable=True)
    website_text_preview = Column(Text, nullable=True)
    context_hash = Column(String, nullable=True)
    completeness_score = Column(Integer, nullable=True)
    company_discovery_status = Column(String, nullable=True)
    assembly_progress_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project = relationship("Project", back_populates="context")


class ProjectChatMessage(Base):
    __tablename__ = "project_chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class FundingProgramSource(Base):
    __tablename__ = "funding_program_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    funding_program_id = Column(
        Integer, ForeignKey("funding_programs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    url = Column(String, nullable=False)
    label = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    funding_program = relationship("FundingProgram", backref="sources")


class KnowledgeBaseDocument(Base):
    __tablename__ = "knowledge_base_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    program_tag = Column(String, nullable=True, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), nullable=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("funding_program_sources.id", ondelete="CASCADE"), nullable=True, index=True)
    uploaded_by = Column(String, ForeignKey("users.email", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    file = relationship("File", backref="knowledge_base_documents")
    source = relationship("FundingProgramSource", backref="kb_document")
    chunks = relationship("KnowledgeBaseChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeBaseChunk(Base):
    __tablename__ = "knowledge_base_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_base_documents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("KnowledgeBaseDocument", back_populates="chunks")
