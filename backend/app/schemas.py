from enum import Enum
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, v: str) -> str:
        v_lower = v.lower()
        # Explicitly allow donotreply@aiio.de
        if v_lower == "donotreply@aiio.de":
            return v_lower
        # Allow emails ending with @innovo-consulting.de or @aiio.de
        if not (v_lower.endswith("@innovo-consulting.de") or v_lower.endswith("@aiio.de")):
            raise ValueError("Email must end with @innovo-consulting.de or @aiio.de")
        return v_lower

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

class UserLogin(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    message: str

class TokenResponse(BaseModel):
    """Response model for login endpoint - includes JWT token"""
    access_token: str
    token_type: str = "bearer"
    success: bool
    message: str

class PasswordResetRequest(BaseModel):
    """Request model for password reset initiation"""
    email: str

class PasswordReset(BaseModel):
    """Request model for password reset completion"""
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

# Funding Program Schemas
class FundingProgramCreate(BaseModel):
    title: str
    website: Optional[str] = None

class FundingProgramResponse(BaseModel):
    id: int
    title: str
    website: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Company Schemas
class CompanyCreate(BaseModel):
    name: str
    website: Optional[str] = None
    audio_path: Optional[str] = None

class CompanyResponse(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    audio_path: Optional[str] = None
    website_text: Optional[str] = None
    transcript_text: Optional[str] = None
    processing_status: str = "pending"
    processing_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Document Schemas
class SectionType(str, Enum):
    TEXT = "text"
    MILESTONE_TABLE = "milestone_table"

class DocumentSection(BaseModel):
    id: str
    title: str
    content: str
    type: Optional[SectionType] = None  # Optional for backward compatibility

class DocumentContent(BaseModel):
    sections: list[DocumentSection]

class DocumentResponse(BaseModel):
    id: int
    company_id: int
    type: str
    content_json: dict
    chat_history: Optional[list[dict]] = None  # Chat messages history
    headings_confirmed: bool = False  # Phase 2.6: Headings confirmation flag
    template_id: Optional[str] = None  # User template UUID (as string)
    template_name: Optional[str] = None  # System template name
    title: Optional[str] = None  # Optional title to distinguish documents
    updated_at: datetime

    @field_validator("template_id", mode="before")
    @classmethod
    def coerce_template_id_to_str(cls, v: object) -> Optional[str]:
        """Coerce UUID to str when returning from ORM (user templates). Leaves None unchanged (system templates)."""
        if v is None:
            return None
        return str(v)

    class Config:
        from_attributes = True

class DocumentUpdate(BaseModel):
    content_json: dict

class DocumentListItem(BaseModel):
    """Response model for listing documents - includes company and funding program info"""
    id: int
    company_id: int
    company_name: str
    funding_program_id: Optional[int] = None
    funding_program_title: Optional[str] = None
    type: str
    title: Optional[str] = None  # Optional title to distinguish documents
    updated_at: datetime

    class Config:
        from_attributes = True

# Chat Schemas
class ChatRequest(BaseModel):
    message: str
    last_edited_sections: Optional[list[str]] = None  # Optional context for clarification suggestions
    conversation_history: Optional[list[dict]] = None  # Optional conversation history for context

class ChatResponse(BaseModel):
    message: str
    updated_sections: Optional[list[str]] = None  # List of section IDs that were updated
    is_question: Optional[bool] = False  # True if this is a question answer (not an edit)
    suggested_content: Optional[dict[str, str]] = None  # Map of section_id -> suggested_content for preview
    requires_confirmation: Optional[bool] = False  # True if user needs to confirm before saving

class ChatConfirmationRequest(BaseModel):
    section_id: str
    confirmed_content: str  # The content user approved

# UserTemplate Schemas
class UserTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sections: list[dict]  # Same structure as Document.content_json. sections

class UserTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sections: Optional[list[dict]] = None

class UserTemplateResponse(BaseModel):
    id: str  # UUID as string
    name: str
    description: Optional[str] = None
    template_structure: dict  # Contains "sections" key
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Funding Program Document Schemas
class FundingProgramDocumentResponse(BaseModel):
    id: str  # UUID as string
    funding_program_id: int
    file_id: str  # UUID as string
    category: str
    original_filename: str
    display_name: Optional[str] = None
    uploaded_at: datetime
    file_type: str
    file_size: int
    has_extracted_text: bool

    class Config:
        from_attributes = True

class FundingProgramDocumentListResponse(BaseModel):
    documents: List[FundingProgramDocumentResponse]
    categories: dict[str, int]  # Category name -> count

class CompanyDocumentResponse(BaseModel):
    id: str  # UUID as string
    company_id: int
    file_id: str  # UUID as string
    original_filename: str
    display_name: Optional[str] = None
    uploaded_at: datetime
    file_type: str
    file_size: int
    has_extracted_text: bool

    class Config:
        from_attributes = True

class CompanyDocumentListResponse(BaseModel):
    documents: List[CompanyDocumentResponse]

class AlteVorhabensbeschreibungDocumentResponse(BaseModel):
    id: str  # UUID as string
    file_id: str  # UUID as string
    original_filename: str
    uploaded_at: str  # ISO format datetime string
    file_type: str
    file_size: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# v2 Project schemas
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    funding_program_id: Optional[int] = None
    topic: str


class ProjectUpdate(BaseModel):
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    funding_program_id: Optional[int] = None
    topic: Optional[str] = None
    is_archived: Optional[bool] = None
    template_overrides_json: Optional[dict] = None


class ProjectContextPatch(BaseModel):
    company_website: Optional[str] = None
    company_description: Optional[str] = None


class ProjectChatMessageCreate(BaseModel):
    message: str


class ProjectChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectChatHistoryResponse(BaseModel):
    messages: List[ProjectChatMessageResponse]


class ProjectContextResponse(BaseModel):
    id: str
    project_id: str
    company_profile_json: Optional[dict] = None
    funding_rules_json: Optional[dict] = None
    domain_research_json: Optional[dict] = None
    retrieved_examples_json: Optional[dict] = None
    style_profile_json: Optional[dict] = None
    website_text_preview: Optional[str] = None  # plain text, not JSON
    context_hash: Optional[str] = None
    # Phase 2: assembly tracking
    completeness_score: Optional[int] = None
    company_discovery_status: Optional[str] = None
    assembly_progress_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: str
    user_email: str
    company_id: Optional[int] = None
    company_name: Optional[str] = None       # FK-resolved name (Phase 1) or free-text (Phase 2)
    funding_program_id: Optional[int] = None
    funding_program_title: Optional[str] = None
    topic: str
    status: str
    is_archived: bool
    template_overrides_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    context: Optional[ProjectContextResponse] = None

    class Config:
        from_attributes = True


class ProjectListItem(BaseModel):
    id: str
    company_id: Optional[int] = None
    company_name: Optional[str] = None       # FK-resolved name (Phase 1) or free-text (Phase 2)
    funding_program_id: Optional[int] = None
    funding_program_title: Optional[str] = None
    topic: str
    status: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# v2 Project — document & section editing schemas
# ---------------------------------------------------------------------------

class ProjectSectionItem(BaseModel):
    id: str
    title: str
    type: str = "text"
    content: Optional[str] = ""


class ProjectDocumentResponse(BaseModel):
    document_id: int
    sections: List[ProjectSectionItem]
    has_content: bool  # True if any section has non-empty content


class ProjectSectionsUpdate(BaseModel):
    sections: List[ProjectSectionItem]


class ProjectGenerateResponse(BaseModel):
    status: str  # "generating"


class SectionProposeEditRequest(BaseModel):
    instruction: str
    additional_context: Optional[str] = None


class SectionProposeEditResponse(BaseModel):
    section_id: str
    proposed_content: str


class ProjectSectionContentPatch(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Phase 4 — Knowledge Base
# ---------------------------------------------------------------------------

class KnowledgeBaseDocumentResponse(BaseModel):
    id: str          # UUID as string
    filename: str
    category: str
    program_tag: Optional[str] = None
    file_id: Optional[str] = None   # NULL for scrape-sourced docs
    uploaded_by: str
    created_at: datetime

    @field_validator("id", "file_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v: object) -> Optional[str]:
        """Coerce UUID objects to str when reading from ORM (UUID(as_uuid=True) columns)."""
        if v is None:
            return None
        return str(v)

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Phase 4 — Funding Program Sources (web scraping)
# ---------------------------------------------------------------------------

class FundingProgramSourceCreate(BaseModel):
    funding_program_id: int
    url: str
    label: Optional[str] = None


class FundingProgramSourceResponse(BaseModel):
    id: str
    funding_program_id: int
    url: str
    label: Optional[str] = None
    status: str
    last_scraped_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    class Config:
        from_attributes = True
