"""
project_chat router — project-scoped chatbot assistant.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from innovo_backend.shared.database import get_db
from innovo_backend.shared.dependencies import get_current_user
from innovo_backend.shared.models import Project, ProjectChatMessage
from innovo_backend.shared.schemas import (
    ProjectChatHistoryResponse,
    ProjectChatMessageCreate,
    ProjectChatMessageResponse,
)
from innovo_backend.services.projects import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["project-chat"])


def _get_owned_project(project_id: str, user_email: str, db: Session) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_email == user_email,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("/{project_id}/chat", response_model=ProjectChatHistoryResponse)
def get_chat_history(
    project_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _get_owned_project(project_id, current_user.email, db)
    messages = (
        db.query(ProjectChatMessage)
        .filter(ProjectChatMessage.project_id == project_id)
        .order_by(ProjectChatMessage.created_at.asc())
        .all()
    )
    return ProjectChatHistoryResponse(
        messages=[
            ProjectChatMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ]
    )


@router.post("/{project_id}/chat", response_model=ProjectChatMessageResponse)
def post_chat_message(
    project_id: str,
    body: ProjectChatMessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _get_owned_project(project_id, current_user.email, db)

    try:
        assistant_text = chat_service.handle_user_message(
            project_id=project_id,
            user_message=body.message,
            db=db,
        )
    except RuntimeError as exc:
        logger.error("project_chat | %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("project_chat | unexpected error for project_id=%s", project_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate response") from exc

    assistant_msg = (
        db.query(ProjectChatMessage)
        .filter(
            ProjectChatMessage.project_id == project_id,
            ProjectChatMessage.role == "assistant",
        )
        .order_by(ProjectChatMessage.created_at.desc())
        .first()
    )
    return ProjectChatMessageResponse(
        id=assistant_msg.id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        created_at=assistant_msg.created_at,
    )
