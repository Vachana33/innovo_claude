"""
v2 Projects router — CRUD endpoints for the Project entity.

All endpoints require a valid JWT token (current_user dependency).
Documents with project_id = NULL are pre-v2 and are not affected by these endpoints.
"""
import logging
import uuid
import os
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, DATABASE_URL
from app.models import Company, Document, FundingProgram, Project, ProjectContext
from app.schemas import (
    ProjectCreate, ProjectContextPatch, ProjectListItem, ProjectResponse, ProjectUpdate,
    ProjectDocumentResponse, ProjectSectionsUpdate, ProjectGenerateResponse,
    SectionProposeEditRequest, SectionProposeEditResponse, ProjectSectionContentPatch,
    ProjectSectionItem,
)
from app.dependencies import get_current_user
from app.services.context_assembler import assemble_project_context
from app.template_resolver import resolve_template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


def _enrich(project: Project, db: Session) -> dict:
    """
    Build a plain dict from the Project ORM row, then:
    - resolve company_name from the FK if a company_id exists and project.company_name is null
    - resolve funding_program_title from the FK
    - attach the context relationship
    """
    data = {col.name: getattr(project, col.name) for col in project.__table__.columns}
    data["context"] = project.context

    # company_name: prefer the free-text field (Phase 2); fall back to FK-resolved name (Phase 1)
    if not data.get("company_name") and project.company_id:
        company = db.get(Company, project.company_id)
        data["company_name"] = company.name if company else None

    fp = db.get(FundingProgram, project.funding_program_id) if project.funding_program_id else None
    data["funding_program_title"] = fp.title if fp else None

    return data


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = Project(
        id=str(uuid.uuid4()),
        user_email=current_user.email,
        company_id=payload.company_id,
        company_name=payload.company_name,
        funding_program_id=payload.funding_program_id,
        topic=payload.topic,
        status="assembling",
        is_archived=False,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Phase 1: when company_id is provided, create the Document synchronously so that
    # a document row with project_id exists immediately after POST /projects returns.
    # Phase 2 free-text path (company_id=None): the context assembler creates the Document
    # after resolving/creating the Company record in Stage 1.
    if payload.company_id:
        try:
            template = resolve_template("system", "wtt_v1", db, current_user.email)
            sections = template.get("sections", [])
            for section in sections:
                if "content" not in section:
                    section["content"] = ""
        except Exception:
            logger.warning("create_project | failed to resolve wtt_v1 template — using empty sections")
            sections = []
        doc = Document(
            company_id=payload.company_id,
            funding_program_id=payload.funding_program_id,
            type="vorhabensbeschreibung",
            content_json={"sections": sections},
            project_id=project.id,
        )
        db.add(doc)
        db.commit()

    # Dispatch context assembly as a background task.
    # The assembler opens its own DB session and always finishes with status="ready".
    background_tasks.add_task(assemble_project_context, project.id, DATABASE_URL)

    return ProjectResponse(**_enrich(project, db))


@router.get("", response_model=List[ProjectListItem])
def list_projects(
    archived: Optional[bool] = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    projects = db.query(Project).filter(
        Project.user_email == current_user.email,
        Project.is_archived == archived,
    ).order_by(Project.created_at.desc()).all()
    return [ProjectListItem(**_enrich(p, db)) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(**_enrich(project, db))


@router.patch("/{project_id}/context", response_model=ProjectResponse)
def patch_project_context(
    project_id: str,
    payload: ProjectContextPatch,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Inline merge of user-provided company data into ProjectContext.company_profile_json.
    Recalculates completeness_score if the previous discovery status was not_found.
    Does NOT re-run the assembler and does NOT change project.status.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ctx = db.query(ProjectContext).filter(
        ProjectContext.project_id == project.id,
    ).first()
    if not ctx:
        raise HTTPException(status_code=404, detail="Project context not found")

    # Copy existing profile (empty dict if not yet assembled)
    profile: dict = dict(ctx.company_profile_json) if ctx.company_profile_json else {}

    # Merge — existing keys are preserved; provided keys overwrite
    if payload.company_website:
        profile["website"] = payload.company_website
    if payload.company_description:
        profile["description"] = payload.company_description
    profile["source"] = "user_provided"

    ctx.company_profile_json = profile

    # Recalculate completeness score: add company weight if it was previously 0
    previous_status = ctx.company_discovery_status
    ctx.company_discovery_status = "partial"

    if ctx.completeness_score is None:
        ctx.completeness_score = 0
    if previous_status == "not_found":
        ctx.completeness_score += 25

    db.commit()
    db.refresh(project)
    return ProjectResponse(**_enrich(project, db))


@router.post("/{project_id}/context/refresh", response_model=ProjectResponse)
def refresh_project_context(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Re-trigger the full context assembler for a project.
    Sets status to assembling immediately, then runs the assembler in the background.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "assembling"
    db.commit()
    db.refresh(project)

    background_tasks.add_task(assemble_project_context, project.id, DATABASE_URL)
    return ProjectResponse(**_enrich(project, db))


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.company_id is not None:
        project.company_id = payload.company_id
    if payload.company_name is not None:
        project.company_name = payload.company_name
    if payload.funding_program_id is not None:
        project.funding_program_id = payload.funding_program_id
    if payload.topic is not None:
        project.topic = payload.topic
    if payload.is_archived is not None:
        project.is_archived = payload.is_archived
    if payload.template_overrides_json is not None:
        project.template_overrides_json = payload.template_overrides_json

    db.commit()
    db.refresh(project)
    return ProjectResponse(**_enrich(project, db))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


# ---------------------------------------------------------------------------
# Document generation background task
# ---------------------------------------------------------------------------

def _run_project_generation(project_id: str, document_id: int, db_url: str) -> None:
    """
    Background task: generate all document sections for a project.
    Mirrors context_assembler pattern — opens its own session.
    Writes per-batch progress to ctx.assembly_progress_json["generation_batches"].
    Always finishes with project.status = "complete".
    """
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker as _sessionmaker
    from sqlalchemy.orm.attributes import flag_modified
    from openai import OpenAI
    from app.routers.documents import _generate_batch_content  # reuse, not reimplement

    BATCH_SIZE = 4

    engine = create_engine(db_url, pool_pre_ping=True)
    _Session = _sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = _Session()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error("_run_project_generation | project_id=%s not found", project_id)
            return

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error("_run_project_generation | document_id=%s not found", document_id)
            project.status = "complete"
            db.commit()
            return

        ctx = db.query(ProjectContext).filter(ProjectContext.project_id == project_id).first()

        sections = document.content_json.get("sections", [])
        generatable = [s for s in sections if s.get("type") != "milestone_table"]

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("_run_project_generation | OPENAI_API_KEY not set — skipping generation")
            project.status = "complete"
            db.commit()
            return

        client = OpenAI(api_key=api_key)
        batches = [generatable[i:i + BATCH_SIZE] for i in range(0, len(generatable), BATCH_SIZE)]
        progress: dict = {}

        for batch_idx, batch in enumerate(batches):
            batch_key = f"batch_{batch_idx + 1}"
            section_ids = [s.get("id", "") for s in batch]
            progress[batch_key] = {"status": "running", "sections": section_ids}

            # Persist running state immediately so frontend can show it
            if ctx:
                prog = dict(ctx.assembly_progress_json) if ctx.assembly_progress_json else {}
                prog["generation_batches"] = progress
                ctx.assembly_progress_json = prog
                flag_modified(ctx, "assembly_progress_json")
                db.commit()

            try:
                results = _generate_batch_content(
                    client=client,
                    batch_sections=batch,
                    company_name="",  # unused when project_context is provided
                    project_context=ctx,
                )

                # Merge generated content into document sections
                updated_sections = []
                for section in document.content_json.get("sections", []):
                    s = dict(section)
                    if s.get("id") in results:
                        s["content"] = results[s["id"]]
                    updated_sections.append(s)

                document.content_json = {"sections": updated_sections}
                flag_modified(document, "content_json")
                progress[batch_key]["status"] = "done"
                logger.info(
                    "_run_project_generation | project_id=%s %s done sections=%s",
                    project_id, batch_key, section_ids,
                )

            except Exception:
                progress[batch_key]["status"] = "failed"
                logger.exception(
                    "_run_project_generation | project_id=%s %s failed",
                    project_id, batch_key,
                )

            # Persist batch result
            if ctx:
                prog = dict(ctx.assembly_progress_json) if ctx.assembly_progress_json else {}
                prog["generation_batches"] = progress
                ctx.assembly_progress_json = prog
                flag_modified(ctx, "assembly_progress_json")

            db.commit()

        project.status = "complete"
        db.commit()
        logger.info(
            "_run_project_generation | project_id=%s complete total_batches=%d",
            project_id, len(batches),
        )

    except Exception:
        logger.exception("_run_project_generation | unhandled error project_id=%s", project_id)
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = "complete"
                db.commit()
        except Exception:
            logger.exception(
                "_run_project_generation | failed to set status=complete project_id=%s", project_id
            )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Document & section endpoints
# ---------------------------------------------------------------------------

@router.get("/{project_id}/document", response_model=ProjectDocumentResponse)
def get_project_document(
    project_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the document linked to this project with its sections and content."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    document = db.query(Document).filter(Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not yet created for this project")

    sections = document.content_json.get("sections", [])
    has_content = any(bool((s.get("content") or "").strip()) for s in sections)
    return ProjectDocumentResponse(
        document_id=document.id,
        sections=[ProjectSectionItem(**s) for s in sections],
        has_content=has_content,
    )


@router.patch("/{project_id}/sections", response_model=ProjectDocumentResponse)
def update_project_sections(
    project_id: str,
    payload: ProjectSectionsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Update section headings before generation (preview mode).
    Only allowed when project.status == 'ready'.
    Preserves existing content for sections that already have it.
    """
    from sqlalchemy.orm.attributes import flag_modified

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Sections can only be updated when project status is 'ready' (current: '{project.status}')",
        )

    document = db.query(Document).filter(Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Preserve existing content for any section that already has it
    existing_content: dict = {
        s.get("id"): s.get("content", "")
        for s in document.content_json.get("sections", [])
    }

    updated_sections = []
    for s in payload.sections:
        sd = s.model_dump()
        sd["content"] = existing_content.get(s.id) or sd.get("content") or ""
        updated_sections.append(sd)

    document.content_json = {"sections": updated_sections}
    flag_modified(document, "content_json")
    db.commit()

    has_content = any(bool((s.get("content") or "").strip()) for s in updated_sections)
    return ProjectDocumentResponse(
        document_id=document.id,
        sections=[ProjectSectionItem(**s) for s in updated_sections],
        has_content=has_content,
    )


@router.post("/{project_id}/generate", response_model=ProjectGenerateResponse)
def generate_project_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Trigger document generation as a background task.
    Requires project.status == 'ready'.
    Sets status = 'generating' immediately and returns.
    Poll GET /projects/{id} to track progress via assembly_progress_json.generation_batches.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot generate: project status is '{project.status}', expected 'ready'",
        )

    document = db.query(Document).filter(Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found for this project")

    project.status = "generating"
    db.commit()

    background_tasks.add_task(_run_project_generation, project_id, document.id, DATABASE_URL)
    return ProjectGenerateResponse(status="generating")


@router.post(
    "/{project_id}/sections/{section_id}/propose-edit",
    response_model=SectionProposeEditResponse,
)
def propose_section_edit(
    project_id: str,
    section_id: str,
    payload: SectionProposeEditRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Propose a text edit for one section without saving.
    Delegates to the existing _generate_section_content logic.
    The caller decides whether to accept (PATCH) or reject (discard).
    """
    import os
    from openai import OpenAI
    from app.routers.documents import _generate_section_content  # reuse, not reimplement

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    document = db.query(Document).filter(Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    sections = document.content_json.get("sections", [])
    target = next((s for s in sections if s.get("id") == section_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    client = OpenAI(api_key=api_key)
    ctx = db.query(ProjectContext).filter(ProjectContext.project_id == project_id).first()

    instruction = payload.instruction
    if payload.additional_context:
        instruction = f"{instruction}\n\nAdditional context:\n{payload.additional_context}"

    proposed = _generate_section_content(
        client=client,
        section_id=section_id,
        section_title=target.get("title", ""),
        current_content=target.get("content", ""),
        instruction=instruction,
        company_name="",  # unused when project_context is provided
        project_context=ctx,
    )
    return SectionProposeEditResponse(section_id=section_id, proposed_content=proposed)


@router.patch(
    "/{project_id}/sections/{section_id}",
    response_model=ProjectDocumentResponse,
)
def accept_section_edit(
    project_id: str,
    section_id: str,
    payload: ProjectSectionContentPatch,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Save accepted content for a specific section.
    Used after the user accepts a proposed edit from propose-edit.
    """
    from sqlalchemy.orm.attributes import flag_modified

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    document = db.query(Document).filter(Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    sections = document.content_json.get("sections", [])
    found = False
    updated_sections = []
    for s in sections:
        if s.get("id") == section_id:
            updated = dict(s)
            updated["content"] = payload.content
            updated_sections.append(updated)
            found = True
        else:
            updated_sections.append(dict(s))

    if not found:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")

    document.content_json = {"sections": updated_sections}
    flag_modified(document, "content_json")
    db.commit()

    has_content = any(bool((s.get("content") or "").strip()) for s in updated_sections)
    return ProjectDocumentResponse(
        document_id=document.id,
        sections=[ProjectSectionItem(**s) for s in updated_sections],
        has_content=has_content,
    )
