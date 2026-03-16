"""
v2 Projects router — CRUD endpoints for the Project entity.

All endpoints require a valid JWT token (current_user dependency).
Documents with project_id = NULL are pre-v2 and are not affected by these endpoints.
"""
import json
import logging
import uuid
import os
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, DATABASE_URL
from app.models import Company, Document, FundingProgram, Project, ProjectContext
from app.schemas import ProjectCreate, ProjectContextPatch, ProjectListItem, ProjectResponse, ProjectUpdate
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

    # Parse existing profile (empty dict if not yet assembled)
    profile: dict = {}
    if ctx.company_profile_json:
        profile = json.loads(ctx.company_profile_json)

    # Merge — existing keys are preserved; provided keys overwrite
    if payload.company_website:
        profile["website"] = payload.company_website
    if payload.company_description:
        profile["description"] = payload.company_description
    profile["source"] = "user_provided"

    ctx.company_profile_json = json.dumps(profile)

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
