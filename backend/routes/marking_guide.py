from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
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


@router.post("/exams/{exam_id}/generate-guide", response_model=GenerateGuideResponse)
async def generate_marking_guide(
    exam_id: str,
    request: GenerateGuideRequest = GenerateGuideRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate marking guide from extracted text using LLM."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get question paper text
    question_doc = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "question_paper"
    ).first()
    
    # Get answer scheme text
    scheme_doc = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "answer_scheme"
    ).first()
    
    # Gather extracted text (order by page then display_order so order matches document)
    question_text = ""
    if question_doc:
        texts = db.query(ExtractedText).filter(
            ExtractedText.document_id == question_doc.id
        ).order_by(ExtractedText.page_number, ExtractedText.display_order).all()
        question_text = "\n".join([
            t.processed_text or t.raw_text or ""
            for t in texts
        ])
    
    scheme_text = ""
    if scheme_doc:
        texts = db.query(ExtractedText).filter(
            ExtractedText.document_id == scheme_doc.id
        ).order_by(ExtractedText.page_number, ExtractedText.display_order).all()
        scheme_text = "\n".join([
            t.processed_text or t.raw_text or ""
            for t in texts
        ])
    
    if not question_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text from question paper. Process documents first."
        )
    
    # Delete existing marking guide for this exam
    db.query(MarkingGuide).filter(MarkingGuide.exam_id == exam_id).delete()
    
    if request.use_llm:
        try:
            result = await llm_service.generate_marking_guide(question_text, scheme_text)
            
            # Save LLM response
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
            
            # Parse and save marking guide (LLM may return array or object with list inside)
            raw = result.parsed_response
            if isinstance(raw, list):
                questions = raw
            elif isinstance(raw, dict):
                questions = (
                    raw.get("questions")
                    or raw.get("marking_guide")
                    or raw.get("items")
                    or raw.get("guide")
                    or []
                )
                if not isinstance(questions, list):
                    questions = []
            else:
                questions = []
            
            for q in questions:
                guide = MarkingGuide(
                    exam_id=exam_id,
                    question_number=str(q.get("question_number", "")),
                    question_text=q.get("question_text"),
                    question_type=_normalize_question_type(q.get("question_type")),
                    answer_scheme=q.get("answer_scheme"),
                    max_marks=float(q.get("max_marks", 0)) if q.get("max_marks") else None
                )
                db.add(guide)
            
            db.commit()
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate guide: {str(e)}")
    
    # Fetch created guides
    guides = db.query(MarkingGuide).filter(
        MarkingGuide.exam_id == exam_id
    ).order_by(MarkingGuide.question_number).all()
    
    total_marks = sum(float(g.max_marks or 0) for g in guides)
    
    return GenerateGuideResponse(
        exam_id=exam_id,
        questions_generated=len(guides),
        total_marks=total_marks,
        marking_guide=[MarkingGuideResponse.model_validate(g) for g in guides]
    )


@router.get("/exams/{exam_id}/marking-guide", response_model=List[MarkingGuideResponse])
async def get_marking_guide(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get marking guide for an exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    guides = db.query(MarkingGuide).filter(
        MarkingGuide.exam_id == exam_id
    ).order_by(MarkingGuide.question_number).all()
    
    return guides


@router.post("/exams/{exam_id}/marking-guide", response_model=MarkingGuideResponse, status_code=201)
async def add_question(
    exam_id: str,
    question: MarkingGuideCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new question to the marking guide."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    guide = MarkingGuide(
        exam_id=exam_id,
        question_number=question.question_number,
        question_text=question.question_text,
        question_type=_normalize_question_type(question.question_type),
        answer_scheme=question.answer_scheme,
        max_marks=question.max_marks,
        is_modified=True
    )
    
    db.add(guide)
    db.commit()
    db.refresh(guide)
    
    return guide


@router.get("/marking-guide/{guide_id}", response_model=MarkingGuideResponse)
async def get_question(
    guide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific question from marking guide."""
    guide = db.query(MarkingGuide).join(Exam).filter(
        MarkingGuide.id == guide_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Question not found")
    
    return guide


@router.put("/marking-guide/{guide_id}", response_model=MarkingGuideResponse)
async def update_question(
    guide_id: str,
    update: MarkingGuideUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a question in the marking guide."""
    guide = db.query(MarkingGuide).join(Exam).filter(
        MarkingGuide.id == guide_id,
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
    
    return guide


@router.delete("/marking-guide/{guide_id}", status_code=204)
async def delete_question(
    guide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a question from the marking guide."""
    guide = db.query(MarkingGuide).join(Exam).filter(
        MarkingGuide.id == guide_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not guide:
        raise HTTPException(status_code=404, detail="Question not found")
    
    db.delete(guide)
    db.commit()
    
    return None
