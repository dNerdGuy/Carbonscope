"""Questionnaire upload, extraction, review, and export routes."""

from __future__ import annotations

import io
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import get_db
from api.deps import get_current_user, require_credits
from api.models import Questionnaire, QuestionnaireQuestion, User, _utcnow
from api.schemas import (
    PaginatedResponse,
    QuestionnaireDetail,
    QuestionnaireOut,
    QuestionnaireUpdate,
    QuestionOut,
    QuestionUpdate,
)
from api.services.questionnaire import extract_text, process_questionnaire
from api.services.templates import get_template, list_templates
from api.services import audit
from api.limiter import limiter
from api.config import RATE_LIMIT_DEFAULT

router = APIRouter(prefix="/questionnaires", tags=["questionnaires"])

_ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/csv": "csv",
}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Magic byte signatures for file type verification
_MAGIC_BYTES = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",  # ZIP archive (used by OOXML)
    "xlsx": b"PK\x03\x04",
}


@router.post("/upload", response_model=QuestionnaireOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def upload_questionnaire(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a sustainability questionnaire document (PDF, DOCX, XLSX, CSV)."""
    content_type = file.content_type or ""
    file_type = _ALLOWED_TYPES.get(content_type)

    # Fallback: check extension
    if not file_type and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        ext_map = {"pdf": "pdf", "docx": "docx", "xlsx": "xlsx", "csv": "csv"}
        file_type = ext_map.get(ext)

    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: PDF, DOCX, XLSX, CSV",
        )

    # Read file in chunks to reject oversized uploads early
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(64 * 1024)  # 64 KB
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {_MAX_FILE_SIZE // (1024*1024)} MB",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Verify magic bytes to prevent disguised file uploads
    expected_magic = _MAGIC_BYTES.get(file_type)
    if expected_magic and not content.startswith(expected_magic):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content does not match expected {file_type.upper()} format",
        )

    extracted_text = extract_text(content, file_type)

    raw_name = file.filename or 'unknown'
    raw_name = raw_name.split('/')[-1].split('\\')[-1]  # strip path components
    safe_name = re.sub(r'[^\w\s.\-]', '_', raw_name)[:255]

    questionnaire = Questionnaire(
        company_id=user.company_id,
        title=safe_name,
        original_filename=safe_name,
        file_type=file_type,
        file_size=total_size,
        status="uploaded",
        extracted_text=extracted_text,
    )
    db.add(questionnaire)
    await db.flush()

    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="questionnaire_upload", resource_type="questionnaire",
        resource_id=str(questionnaire.id),
    )
    await db.commit()
    await db.refresh(questionnaire)

    return questionnaire


@router.get("/", response_model=PaginatedResponse[QuestionnaireOut])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_questionnaires(
    request: Request,
    status: str | None = Query(default=None, pattern="^(uploaded|extracting|extracted|reviewed|exported)$"),
    file_type: str | None = Query(default=None, pattern="^(pdf|xlsx|docx|csv)$"),
    sort_by: str = Query(default="created_at", pattern="^(created_at|updated_at|title)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List questionnaires for the current user's company."""
    base = select(Questionnaire).where(
        Questionnaire.company_id == user.company_id,
        Questionnaire.deleted_at.is_(None),
    )
    if status is not None:
        base = base.where(Questionnaire.status == status)
    if file_type is not None:
        base = base.where(Questionnaire.file_type == file_type)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    sort_col = getattr(Questionnaire, sort_by)
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()
    rows = (
        await db.execute(base.order_by(sort_expr).offset(offset).limit(limit))
    ).scalars().all()

    return PaginatedResponse[QuestionnaireOut](
        items=[QuestionnaireOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── Template library ────────────────────────────────────────────────
# NOTE: Template routes MUST be defined before /{questionnaire_id}
# to prevent FastAPI from matching "templates" as a questionnaire ID.


@router.get("/templates/", response_model=list)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_templates(
    request: Request,
    user: User = Depends(get_current_user),
):
    """List available pre-built questionnaire templates."""
    return list_templates()


@router.get("/templates/{template_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_template_detail(
    request: Request,
    template_id: str,
    user: User = Depends(get_current_user),
):
    """Get a specific questionnaire template with all questions."""
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tpl


@router.post("/templates/{template_id}/apply", response_model=QuestionnaireDetail)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def apply_template(
    request: Request,
    template_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a questionnaire from a pre-built template and generate draft answers."""
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    questionnaire = Questionnaire(
        company_id=user.company_id,
        title=tpl["title"],
        original_filename=f"template:{template_id}",
        file_type="template",
        file_size=0,
        status="extracted",
        extracted_text="",
    )
    db.add(questionnaire)
    await db.flush()

    # Get company data for draft answers
    from api.models import Company, EmissionReport
    from api.services.questionnaire import generate_draft_answer

    company_result = await db.execute(
        select(Company).where(Company.id == user.company_id, Company.deleted_at.is_(None))
    )
    company = company_result.scalar_one()

    report_result = await db.execute(
        select(EmissionReport)
        .where(
            EmissionReport.company_id == user.company_id,
            EmissionReport.deleted_at.is_(None),
        )
        .order_by(EmissionReport.created_at.desc())
        .limit(1)
    )
    report = report_result.scalar_one_or_none()

    questions_out = []
    for i, q in enumerate(tpl["questions"], start=1):
        draft, confidence = await generate_draft_answer(
            question=q["question_text"],
            company_name=company.name,
            industry=company.industry,
            region=company.region,
            scope1=report.scope1 if report else 0,
            scope2=report.scope2 if report else 0,
            scope3=report.scope3 if report else 0,
            total=report.total if report else 0,
        )
        question = QuestionnaireQuestion(
            questionnaire_id=questionnaire.id,
            question_number=i,
            question_text=q["question_text"],
            category=q.get("category"),
            ai_draft_answer=draft,
            confidence=confidence,
        )
        db.add(question)
        await db.flush()
        questions_out.append(QuestionOut.model_validate(question))

    await db.commit()
    await db.refresh(questionnaire)

    return QuestionnaireDetail(
        questionnaire=QuestionnaireOut.model_validate(questionnaire),
        questions=questions_out,
    )


# ── Individual questionnaire operations ──────────────────────────────


@router.get("/{questionnaire_id}", response_model=QuestionnaireDetail)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_questionnaire(
    request: Request,
    questionnaire_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get questionnaire with all extracted questions."""
    result = await db.execute(
        select(Questionnaire)
        .options(selectinload(Questionnaire.questions))
        .where(
            Questionnaire.id == questionnaire_id,
            Questionnaire.company_id == user.company_id,
            Questionnaire.deleted_at.is_(None),
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionnaire not found")

    questions_sorted = sorted(q.questions, key=lambda x: x.question_number)
    return QuestionnaireDetail(
        questionnaire=QuestionnaireOut.model_validate(q),
        questions=[QuestionOut.model_validate(qu) for qu in questions_sorted],
    )


@router.post("/{questionnaire_id}/extract", response_model=QuestionnaireDetail)
@limiter.limit("5/minute")
async def extract_questions(
    request: Request,
    questionnaire_id: str,
    user: User = Depends(require_credits("questionnaire_extract")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI extraction of questions + draft answer generation."""
    result = await db.execute(
        select(Questionnaire).where(
            Questionnaire.id == questionnaire_id,
            Questionnaire.company_id == user.company_id,
            Questionnaire.deleted_at.is_(None),
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionnaire not found")

    if q.status not in ("uploaded", "extracted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot extract from questionnaire in status '{q.status}'",
        )

    await process_questionnaire(db, questionnaire_id, user.company_id)

    # Deduct credits only after extraction succeeded
    from api.services.subscriptions import deduct_operation_credits
    await deduct_operation_credits(db, user.company_id, "questionnaire_extract")
    await db.commit()

    # Re-fetch with questions
    result = await db.execute(
        select(Questionnaire)
        .options(selectinload(Questionnaire.questions))
        .where(Questionnaire.id == questionnaire_id)
    )
    q = result.scalar_one()
    questions_sorted = sorted(q.questions, key=lambda x: x.question_number)
    return QuestionnaireDetail(
        questionnaire=QuestionnaireOut.model_validate(q),
        questions=[QuestionOut.model_validate(qu) for qu in questions_sorted],
    )


@router.patch("/{questionnaire_id}/questions/{question_id}", response_model=QuestionOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_question(
    request: Request,
    questionnaire_id: str,
    question_id: str,
    body: QuestionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a question's human answer or approval status."""
    # Verify ownership
    q_result = await db.execute(
        select(Questionnaire).where(
            Questionnaire.id == questionnaire_id,
            Questionnaire.company_id == user.company_id,
            Questionnaire.deleted_at.is_(None),
        )
    )
    if not q_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionnaire not found")

    result = await db.execute(
        select(QuestionnaireQuestion).where(
            QuestionnaireQuestion.id == question_id,
            QuestionnaireQuestion.questionnaire_id == questionnaire_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    if body.human_answer is not None:
        question.human_answer = body.human_answer
    if body.status is not None:
        question.status = body.status

    await db.commit()
    await db.refresh(question)
    return question


@router.delete("/{questionnaire_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def delete_questionnaire(
    request: Request,
    questionnaire_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a questionnaire."""
    result = await db.execute(
        select(Questionnaire).where(
            Questionnaire.id == questionnaire_id,
            Questionnaire.company_id == user.company_id,
            Questionnaire.deleted_at.is_(None),
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionnaire not found")
    q.deleted_at = _utcnow()

    await audit.record(
        db, user_id=user.id, company_id=user.company_id,
        action="questionnaire_delete", resource_type="questionnaire",
        resource_id=questionnaire_id,
    )

    await db.commit()


@router.patch("/{questionnaire_id}", response_model=QuestionnaireOut)
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_questionnaire(
    request: Request,
    questionnaire_id: str,
    body: QuestionnaireUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a questionnaire's title or status."""
    result = await db.execute(
        select(Questionnaire).where(
            Questionnaire.id == questionnaire_id,
            Questionnaire.company_id == user.company_id,
            Questionnaire.deleted_at.is_(None),
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionnaire not found")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(q, key, value)

    await db.commit()
    await db.refresh(q)
    return q


@router.get("/{questionnaire_id}/export/pdf")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def export_questionnaire_pdf(
    request: Request,
    questionnaire_id: str,
    user: User = Depends(require_credits("pdf_export")),
    db: AsyncSession = Depends(get_db),
):
    """Export questionnaire responses as a styled PDF."""
    from api.models import Company
    from api.services.pdf_export import generate_questionnaire_pdf

    result = await db.execute(
        select(Questionnaire)
        .options(selectinload(Questionnaire.questions))
        .where(
            Questionnaire.id == questionnaire_id,
            Questionnaire.company_id == user.company_id,
            Questionnaire.deleted_at.is_(None),
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionnaire not found")

    company_result = await db.execute(select(Company).where(Company.id == user.company_id, Company.deleted_at.is_(None)))
    company = company_result.scalar_one()

    questions_data = sorted(
        [
            {
                "question_number": qu.question_number,
                "question_text": qu.question_text,
                "category": qu.category,
                "ai_draft_answer": qu.ai_draft_answer,
                "human_answer": qu.human_answer,
                "status": qu.status,
            }
            for qu in q.questions
        ],
        key=lambda x: x["question_number"],
    )

    pdf_bytes = generate_questionnaire_pdf(
        company_name=company.name,
        questionnaire_title=q.title,
        questions=questions_data,
    )

    # Deduct credits only after PDF generation succeeded
    from api.services.subscriptions import deduct_operation_credits
    await deduct_operation_credits(db, user.company_id, "pdf_export")
    await db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=questionnaire_{questionnaire_id[:8]}.pdf"},
    )
