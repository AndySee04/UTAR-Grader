from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.extracted_text import ExtractedText
from models.questions import Question
from models.marking_guide import MarkingGuide
from models.llm_response import LLMResponse
from schemas.marking_guide import (
    MarkingGuideCreate, MarkingGuideUpdate, MarkingGuideResponse,
    GenerateGuideRequest, GenerateGuideResponse
)
from utils.auth import get_current_user
from services.llm_service import llm_service

router = APIRouter()


def _normalize_question_type(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip().lower()
    if raw in {"mcq", "structured", "open_ended"}:
        return raw
    return None


def _to_response(guide: MarkingGuide) -> MarkingGuideResponse:
    q = guide.question
    return MarkingGuideResponse(
        id=str(guide.id),
        exam_id=str(guide.exam_id),
        question_number=(q.question_number if q else "") or "",
        question_text=(q.question_text if q else None),
        question_type=guide.question_type,
        answer_scheme=guide.answer_scheme,
        max_marks=float(guide.max_marks) if guide.max_marks is not None else None,
        is_modified=bool(guide.is_modified),
        created_at=guide.created_at,
        modified_at=guide.modified_at,
    )


def _get_or_create_question(db: Session, exam_id: str, question_number: str, question_text: str | None) -> Question:
    qnum = (question_number or "").strip()
    if not qnum:
        raise HTTPException(status_code=400, detail="question_number is required")
    q = db.query(Question).filter(
        Question.exam_id == exam_id,
        Question.question_number == qnum
    ).first()
    if not q:
        q = Question(
            exam_id=exam_id,
            question_number=qnum,
            question_text=question_text
        )
        db.add(q)
        db.flush()
    elif question_text is not None:
        q.question_text = question_text
    return q


@router.post("/exams/{exam_id}/generate-guide", response_model=GenerateGuideResponse)
async def generate_marking_guide(
    exam_id: str,
    request: GenerateGuideRequest = GenerateGuideRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    question_doc = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "question_paper"
    ).first()
    scheme_doc = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "answer_scheme"
    ).first()

    question_text = ""
    if question_doc:
        texts = db.query(ExtractedText).filter(
            ExtractedText.document_id == question_doc.id
        ).order_by(ExtractedText.page_number, ExtractedText.display_order).all()
        question_text = "\n".join([(t.processed_text or t.raw_text or "") for t in texts])

    scheme_text = ""
    if scheme_doc:
        texts = db.query(ExtractedText).filter(
            ExtractedText.document_id == scheme_doc.id
        ).order_by(ExtractedText.page_number, ExtractedText.display_order).all()
        scheme_text = "\n".join([(t.processed_text or t.raw_text or "") for t in texts])

    if not question_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text from question paper. Process documents first."
        )

    db.query(MarkingGuide).filter(MarkingGuide.exam_id == exam_id).delete()

    if request.use_llm:
        try:
            result = await llm_service.generate_marking_guide(question_text, scheme_text)
            llm_response = LLMResponse(
                exam_id=exam_id,
                request_type="guide_generation",
                input_text=f"QUESTIONS:\n{question_text}\n\nSCHEME:\n{scheme_text}",
                raw_response=result.raw_response,
                parsed_response=result.parsed_response,
                model_used=result.model_used,
                processing_time_ms=result.processing_time_ms,
                tokens_used=result.tokens_used
            )
            db.add(llm_response)

            raw = result.parsed_response
            if isinstance(raw, list):
                items = raw
            elif isinstance(raw, dict):
                items = raw.get("questions") or raw.get("marking_guide") or raw.get("items") or raw.get("guide") or []
                if not isinstance(items, list):
                    items = []
            else:
                items = []

            for item in items:
                q = _get_or_create_question(
                    db,
                    exam_id=exam_id,
                    question_number=str(item.get("question_number", "")),
                    question_text=item.get("question_text")
                )
                db.add(MarkingGuide(
                    exam_id=exam_id,
                    question_id=q.id,
                    question_type=_normalize_question_type(item.get("question_type")),
                    answer_scheme=item.get("answer_scheme"),
                    max_marks=float(item.get("max_marks", 0)) if item.get("max_marks") else None
                ))
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate guide: {str(e)}")

    guides = db.query(MarkingGuide).join(Question).filter(
        MarkingGuide.exam_id == exam_id
    ).order_by(Question.question_number).all()
    total_marks = sum(float(g.max_marks or 0) for g in guides)
    return GenerateGuideResponse(
        exam_id=exam_id,
        questions_generated=len(guides),
        total_marks=total_marks,
        marking_guide=[_to_response(g) for g in guides]
    )


@router.get("/exams/{exam_id}/marking-guide", response_model=List[MarkingGuideResponse])
async def get_marking_guide(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    guides = db.query(MarkingGuide).join(Question).filter(
        MarkingGuide.exam_id == exam_id
    ).order_by(Question.question_number).all()
    return [_to_response(g) for g in guides]


@router.post("/exams/{exam_id}/marking-guide", response_model=MarkingGuideResponse, status_code=201)
async def add_question(
    exam_id: str,
    question: MarkingGuideCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    q = _get_or_create_question(db, exam_id, question.question_number, question.question_text)
    guide = MarkingGuide(
        exam_id=exam_id,
        question_id=q.id,
        question_type=_normalize_question_type(question.question_type),
        answer_scheme=question.answer_scheme,
        max_marks=question.max_marks,
        is_modified=True
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return _to_response(guide)


@router.get("/marking-guide/{guide_id}", response_model=MarkingGuideResponse)
async def get_question(
    guide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    guide = db.query(MarkingGuide).join(Exam).filter(
        MarkingGuide.id == guide_id,
        Exam.user_id == current_user.id
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Question not found")
    return _to_response(guide)


@router.put("/marking-guide/{guide_id}", response_model=MarkingGuideResponse)
async def update_question(
    guide_id: str,
    update: MarkingGuideUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    guide = db.query(MarkingGuide).join(Exam).filter(
        MarkingGuide.id == guide_id,
        Exam.user_id == current_user.id
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Question not found")

    q = guide.question
    if update.question_number is not None:
        q.question_number = update.question_number
    if update.question_text is not None:
        q.question_text = update.question_text
    if update.question_type is not None:
        guide.question_type = _normalize_question_type(update.question_type)
    if update.answer_scheme is not None:
        guide.answer_scheme = update.answer_scheme
    if update.max_marks is not None:
        guide.max_marks = update.max_marks
    guide.is_modified = True
    guide.modified_at = datetime.utcnow()
    db.commit()
    db.refresh(guide)
    return _to_response(guide)


@router.delete("/marking-guide/{guide_id}", status_code=204)
async def delete_question(
    guide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    guide = db.query(MarkingGuide).join(Exam).filter(
        MarkingGuide.id == guide_id,
        Exam.user_id == current_user.id
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(guide)
    db.commit()
    return None
