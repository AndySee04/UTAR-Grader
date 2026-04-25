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
from models.question import Question
from schemas.marking_guide import (
    MarkingGuideCreate, MarkingGuideUpdate, MarkingGuideResponse
)
from utils.auth import get_current_user

router = APIRouter()


def _normalize_question_type(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip().lower()
    if raw in {"mcq", "structured", "open_ended"}:
        return raw
    return None


def _to_response(q: Question) -> MarkingGuideResponse:
    return MarkingGuideResponse(
        id=str(q.id),
        exam_id=str(q.exam_id),
        question_number=(q.question_number or ""),
        question_text=q.question_text,
        question_type=q.question_type,
        answer_scheme=q.answer_scheme,
        max_marks=float(q.max_marks) if q.max_marks is not None else None,
        is_modified=bool(q.is_modified),
        created_at=q.created_at,
        modified_at=q.modified_at,
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

    guides = db.query(Question).filter(
        Question.exam_id == exam_id
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
    q.question_type = _normalize_question_type(question.question_type)
    q.answer_scheme = question.answer_scheme
    q.max_marks = question.max_marks
    q.is_modified = True
    db.commit()
    db.refresh(q)
    return _to_response(q)


@router.put("/marking-guide/{guide_id}", response_model=MarkingGuideResponse)
async def update_question(
    guide_id: str,
    update: MarkingGuideUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    guide = db.query(Question).join(Exam).filter(
        Question.id == guide_id,
        Exam.user_id == current_user.id
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Question not found")

    if update.question_number is not None:
        guide.question_number = update.question_number
    if update.question_text is not None:
        guide.question_text = update.question_text
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
    guide = db.query(Question).join(Exam).filter(
        Question.id == guide_id,
        Exam.user_id == current_user.id
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(guide)
    db.commit()
    return None
