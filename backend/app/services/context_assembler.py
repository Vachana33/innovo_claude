"""
Phase 2 — Context Assembler

Runs as a FastAPI BackgroundTask after project creation.
Opens its own DB session (required for background tasks that outlive the request).

Invariant: the assembler ALWAYS finishes with project.status = "ready".
It must never leave a project stuck in "assembling", even if a stage fails.

Stage weights (must sum to 100):
    company          25
    funding_rules    25
    domain_research  20
    examples         15
    style            15
"""
import logging
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

CONTEXT_SCORE_WEIGHTS = {
    "company": 25,
    "funding_rules": 25,
    "domain_research": 20,
    "examples": 15,
    "style": 15,
}


def _make_session(db_url: str) -> Session:
    engine = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def _write_progress(ctx, db: Session, stage_key: str, status: str, detail: Optional[str] = None) -> None:
    """Persist an in-progress stage update to assembly_progress_json."""
    progress = dict(ctx.assembly_progress_json) if ctx.assembly_progress_json else {}
    progress[stage_key] = {"status": status}
    if detail:
        progress[stage_key]["detail"] = detail
    ctx.assembly_progress_json = progress
    db.commit()


def assemble_project_context(project_id: str, db_url: str) -> None:
    """
    Assemble all context for a project and write the result to project_contexts.
    Called as a BackgroundTask from POST /projects.
    """
    # Import models here to avoid circular imports at module load time
    from app.models import (
        Project, ProjectContext,
        Company, Document, FundingProgramGuidelinesSummary,
        AlteVorhabensbeschreibungStyleProfile,
    )

    db = _make_session(db_url)
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error("context_assembler | project_id=%s not found — aborting", project_id)
            return

        ctx = db.query(ProjectContext).filter(ProjectContext.project_id == project_id).first()
        if not ctx:
            ctx = ProjectContext(project_id=project_id)
            db.add(ctx)
            db.commit()
            db.refresh(ctx)

        scores: dict[str, int] = {}

        # ------------------------------------------------------------------ #
        # Stage 1 — Company research
        # ------------------------------------------------------------------ #
        try:
            _write_progress(ctx, db, "company", "running")
            company_profile = None
            discovery_status = "not_found"

            if project.company_id:
                company = db.query(Company).filter(Company.id == project.company_id).first()
                if company:
                    if company.company_profile:
                        company_profile = company.company_profile
                        discovery_status = "found"
                    elif company.website_clean_text or company.transcript_clean:
                        # Company exists but extraction hasn't run yet — partial
                        preview = (company.website_clean_text or company.transcript_clean or "")[:30_000]
                        company_profile = {"raw_preview": preview}
                        discovery_status = "partial"
                    else:
                        discovery_status = "partial"

                    # Store website text preview separately
                    if company.website_clean_text:
                        ctx.website_text_preview = company.website_clean_text[:30_000]

            elif project.company_name:
                # Phase 2: free-text company — resolve or create a Company record so that
                # generate_content() can load company data via company_id FK.
                overrides: dict = {}
                if project.template_overrides_json:
                    overrides = project.template_overrides_json

                company_website = overrides.get("company_website")
                company_description = overrides.get("company_description")

                # Case-insensitive name match within the same user's companies
                company = (
                    db.query(Company)
                    .filter(
                        Company.user_email == project.user_email,
                        Company.name.ilike(project.company_name),
                    )
                    .first()
                )
                if not company:
                    company = Company(
                        name=project.company_name,
                        user_email=project.user_email,
                        website=company_website,
                    )
                    db.add(company)
                    db.flush()  # Assign PK without ending the transaction
                elif company_website and not company.website:
                    company.website = company_website

                # Populate company_profile from user-provided data if not already extracted
                if not company.company_profile:
                    profile_data: dict = {"company_name": project.company_name, "source": "user_provided"}
                    if company_description:
                        profile_data["description"] = company_description
                    if company_website:
                        profile_data["website"] = company_website
                    company.company_profile = profile_data

                project.company_id = company.id
                db.commit()
                db.refresh(company)

                company_profile = company.company_profile
                discovery_status = "partial"  # Research Agent (Phase 5) will upgrade this to "found"

            ctx.company_profile_json = company_profile
            ctx.company_discovery_status = discovery_status

            scores["company"] = CONTEXT_SCORE_WEIGHTS["company"] if discovery_status in ("found", "partial") else 0
            _write_progress(ctx, db, "company", "done", discovery_status)
            db.commit()

        except Exception:
            logger.exception("context_assembler | stage=company project_id=%s", project_id)
            scores["company"] = 0
            _write_progress(ctx, db, "company", "failed")

        # ------------------------------------------------------------------ #
        # Stage 2 — Funding program rules
        # ------------------------------------------------------------------ #
        try:
            _write_progress(ctx, db, "funding_rules", "running")
            funding_rules = None

            if project.funding_program_id:
                summary = (
                    db.query(FundingProgramGuidelinesSummary)
                    .filter(FundingProgramGuidelinesSummary.funding_program_id == project.funding_program_id)
                    .first()
                )
                if summary and summary.rules_json:
                    funding_rules = summary.rules_json

            ctx.funding_rules_json = funding_rules
            scores["funding_rules"] = CONTEXT_SCORE_WEIGHTS["funding_rules"] if funding_rules else 0
            _write_progress(ctx, db, "funding_rules", "done",
                            "loaded" if funding_rules else "no_guidelines_uploaded")
            db.commit()

        except Exception:
            logger.exception("context_assembler | stage=funding_rules project_id=%s", project_id)
            scores["funding_rules"] = 0
            _write_progress(ctx, db, "funding_rules", "failed")

        # ------------------------------------------------------------------ #
        # Stage 3 — Domain research (stub — Phase 5 wires the Research Agent)
        # ------------------------------------------------------------------ #
        try:
            _write_progress(ctx, db, "domain_research", "running")
            ctx.domain_research_json = None
            scores["domain_research"] = 0
            _write_progress(ctx, db, "domain_research", "done", "stub")
            db.commit()

        except Exception:
            logger.exception("context_assembler | stage=domain_research project_id=%s", project_id)
            scores["domain_research"] = 0
            _write_progress(ctx, db, "domain_research", "failed")

        # ------------------------------------------------------------------ #
        # Stage 4 — Retrieved examples (Knowledge Base — Phase 4)
        # ------------------------------------------------------------------ #
        try:
            _write_progress(ctx, db, "examples", "running")
            from app.services.knowledge_base_retriever import retrieve_kb_context
            from app.models import FundingProgram

            # Build a semantic query from topic + company name
            query_parts = [project.topic]
            if project.company_name:
                query_parts.append(project.company_name)
            elif ctx.company_profile_json:
                name = ctx.company_profile_json.get("company_name")
                if name:
                    query_parts.append(name)
            query = " ".join(query_parts)

            # Derive program_tag from the linked FundingProgram title.
            # Convention: the admin must use the exact FundingProgram.title as the
            # program_tag when uploading KB documents (e.g. "ZIM", "WTT Fonds").
            # If no tagged documents exist, retrieve_kb_context falls back to unfiltered.
            program_tag = None
            if project.funding_program_id:
                fp = db.query(FundingProgram).filter(
                    FundingProgram.id == project.funding_program_id
                ).first()
                if fp:
                    program_tag = fp.title

            kb_context = retrieve_kb_context(
                query=query,
                db=db,
                program_tag=program_tag,
            )

            has_any = any(kb_context.get(k) for k in ("examples", "guidelines", "domain"))
            ctx.retrieved_examples_json = kb_context if has_any else None
            scores["examples"] = CONTEXT_SCORE_WEIGHTS["examples"] if has_any else 0

            total_chunks = sum(len(kb_context.get(k) or []) for k in ("examples", "guidelines", "domain"))
            _write_progress(ctx, db, "examples", "done",
                            f"{total_chunks}_chunks" if has_any else "no_kb_content")
            db.commit()

        except Exception:
            logger.exception("context_assembler | stage=examples project_id=%s", project_id)
            scores["examples"] = 0
            ctx.retrieved_examples_json = None
            _write_progress(ctx, db, "examples", "failed")

        # ------------------------------------------------------------------ #
        # Stage 5 — Style profile
        # ------------------------------------------------------------------ #
        try:
            _write_progress(ctx, db, "style", "running")
            style_profile = None

            latest_style = (
                db.query(AlteVorhabensbeschreibungStyleProfile)
                .order_by(AlteVorhabensbeschreibungStyleProfile.created_at.desc())
                .first()
            )
            if latest_style and latest_style.style_summary_json:
                style_profile = latest_style.style_summary_json

            ctx.style_profile_json = style_profile
            scores["style"] = CONTEXT_SCORE_WEIGHTS["style"] if style_profile else 0
            _write_progress(ctx, db, "style", "done",
                            "loaded" if style_profile else "no_style_profile_uploaded")
            db.commit()

        except Exception:
            logger.exception("context_assembler | stage=style project_id=%s", project_id)
            scores["style"] = 0
            _write_progress(ctx, db, "style", "failed")

        # ------------------------------------------------------------------ #
        # Consolidation — compute score and mark project ready
        # ------------------------------------------------------------------ #
        ctx.completeness_score = sum(scores.values())
        project.status = "ready"
        db.commit()

        # Create a Document row if this project doesn't have one yet.
        # Requires company_id (set by the upsert above for Phase 2 projects).
        try:
            if project.company_id:
                existing_doc = db.query(Document).filter(Document.project_id == project_id).first()
                if not existing_doc:
                    # Load template sections — document must never be created with empty structure
                    try:
                        from app.template_resolver import resolve_template
                        _tmpl = resolve_template("system", "wtt_v1", db)
                        _tmpl_sections = [
                            {**s, "content": s.get("content", "")}
                            for s in _tmpl.get("sections", [])
                        ]
                    except Exception:
                        logger.warning(
                            "context_assembler | failed to load wtt_v1 — using empty sections project_id=%s",
                            project_id,
                        )
                        _tmpl_sections = []
                    doc = Document(
                        company_id=project.company_id,
                        funding_program_id=project.funding_program_id,
                        type="vorhabensbeschreibung",
                        content_json={"sections": _tmpl_sections},
                        project_id=project_id,
                    )
                    db.add(doc)
                    db.commit()
                    logger.info(
                        "context_assembler | created document project_id=%s company_id=%s sections=%d",
                        project_id, project.company_id, len(_tmpl_sections),
                    )
        except Exception:
            logger.exception("context_assembler | failed to create document project_id=%s", project_id)

        logger.info(
            "context_assembler | project_id=%s status=ready completeness=%s discovery=%s",
            project_id, ctx.completeness_score, ctx.company_discovery_status,
        )

    except Exception:
        # Safety net: always flip to ready so the frontend is never blocked.
        logger.exception("context_assembler | unhandled error project_id=%s — forcing status=ready", project_id)
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = "ready"
                db.commit()
        except Exception:
            logger.exception("context_assembler | failed to force status=ready project_id=%s", project_id)
    finally:
        db.close()
