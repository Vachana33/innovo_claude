"""
v2 Projects router — CRUD endpoints for the Project entity.
"""
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker as _sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from innovo_backend.shared.database import get_db, DATABASE_URL
from innovo_backend.shared.models import Company, Document, FundingProgram, Project, ProjectContext
from innovo_backend.shared.schemas import (
    ProjectCreate, ProjectContextPatch, ProjectListItem, ProjectResponse, ProjectUpdate,
    ProjectDocumentResponse, ProjectSectionsUpdate, ProjectGenerateResponse,
    SectionProposeEditRequest, SectionProposeEditResponse, ProjectSectionContentPatch,
    ProjectSectionItem,
)
from innovo_backend.shared.dependencies import get_current_user
from innovo_backend.services.projects.context_assembler import assemble_project_context
from innovo_backend.shared.template_resolver import resolve_template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


def _enrich(project: Project, db: Session) -> dict:
    data = {col.name: getattr(project, col.name) for col in project.__table__.columns}
    data["context"] = project.context

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
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ctx = db.query(ProjectContext).filter(ProjectContext.project_id == project.id).first()
    if not ctx:
        raise HTTPException(status_code=404, detail="Project context not found")

    profile: dict = dict(ctx.company_profile_json) if ctx.company_profile_json else {}

    if payload.company_website:
        profile["website"] = payload.company_website
    if payload.company_description:
        profile["description"] = payload.company_description
    profile["source"] = "user_provided"

    ctx.company_profile_json = profile

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


def _run_project_generation(project_id: str, document_id: int, db_url: str) -> None:
    """
    Background task: generate all document sections for a project.
    """
    import os  # noqa: PLC0415
    from openai import OpenAI  # noqa: PLC0415

    BATCH_SIZE = 4

    engine = create_engine(db_url, pool_pre_ping=True)
    _Session = _sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = _Session()
    try:
        from innovo_backend.shared.models import Project, Document, ProjectContext  # noqa: PLC0415
        from innovo_backend.services.documents.service import _generate_batch_content  # noqa: PLC0415

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error("_run_project_generation | project_id=%s not found", project_id)
            return

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error("_run_project_generation | document_id=%s not found", document_id)
            return

        ctx = db.query(ProjectContext).filter(ProjectContext.project_id == project_id).first()

        sections = (document.content_json or {}).get("sections", [])

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("_run_project_generation | OPENAI_API_KEY not set")
            project.status = "complete"
            db.commit()
            return

        client = OpenAI(api_key=api_key)

        progress_json = dict(ctx.assembly_progress_json) if ctx and ctx.assembly_progress_json else {}

        for i in range(0, len(sections), BATCH_SIZE):
            batch = sections[i: i + BATCH_SIZE]
            batch_ids = [s.get("id") for s in batch]

            try:
                generated = _generate_batch_content(
                    sections=batch,
                    document=document,
                    project=project,
                    ctx=ctx,
                    client=client,
                    db=db,
                )
                for section in sections:
                    if section.get("id") in generated:
                        section["content"] = generated[section["id"]]

                flag_modified(document, "content_json")
                db.commit()

                progress_json.setdefault("generation_batches", {})[str(i)] = "done"
                if ctx:
                    ctx.assembly_progress_json = progress_json
                    db.commit()

            except Exception:
                logger.exception("_run_project_generation | batch %d failed project_id=%s", i, project_id)
                progress_json.setdefault("generation_batches", {})[str(i)] = "failed"
                if ctx:
                    ctx.assembly_progress_json = progress_json
                    db.commit()

        project.status = "complete"
        db.commit()
        logger.info("_run_project_generation | project_id=%s complete", project_id)

    except Exception:
        logger.exception("_run_project_generation | unhandled error project_id=%s", project_id)
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = "complete"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/{project_id}/generate", response_model=ProjectGenerateResponse)
def generate_project_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == current_user.email,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status not in ("ready", "complete"):
        raise HTTPException(status_code=409, detail=f"Project is not ready for generation (status={project.status})")

    document = db.query(Document).filter(Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Project document not found")

    project.status = "generating"
    db.commit()

    background_tasks.add_task(_run_project_generation, project_id, document.id, DATABASE_URL)

    return ProjectGenerateResponse(project_id=project_id, document_id=document.id, status="generating")
