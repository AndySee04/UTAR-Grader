from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.grade import GradingSummary
from schemas.exam import ExamCreate, ExamUpdate, ExamResponse, ExamListResponse, ExamDetailResponse
from utils.auth import get_current_user

router = APIRouter()


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new exam."""
    new_exam = Exam(
        user_id=current_user.id,
        name=exam_data.name,
        status="draft"
    )
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)
    return new_exam


@router.get("", response_model=List[ExamListResponse])
async def list_exams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all exams for the current user."""
    exams = db.query(Exam).filter(Exam.user_id == current_user.id).order_by(Exam.created_at.desc()).all()
    
    result = []
    for exam in exams:
        doc_count = db.query(Document).filter(Document.exam_id == exam.id).count()
        student_count = db.query(Document).filter(
            Document.exam_id == exam.id,
            Document.doc_type == "student_answer"
        ).count()
        
        result.append(ExamListResponse(
            id=exam.id,
            name=exam.name,
            status=exam.status,
            created_at=exam.created_at,
            completed_at=exam.completed_at,
            document_count=doc_count,
            student_count=student_count
        ))
    
    return result


@router.get("/{exam_id}", response_model=ExamDetailResponse)
async def get_exam(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get exam details by ID."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    doc_count = db.query(Document).filter(Document.exam_id == exam.id).count()
    student_count = db.query(Document).filter(
        Document.exam_id == exam.id,
        Document.doc_type == "student_answer"
    ).count()
    
    # Get grading stats
    graded_count = db.query(GradingSummary).filter(GradingSummary.exam_id == exam.id).count()
    avg_result = db.query(func.avg(GradingSummary.percentage)).filter(
        GradingSummary.exam_id == exam.id
    ).scalar()
    
    return ExamDetailResponse(
        id=exam.id,
        user_id=exam.user_id,
        name=exam.name,
        status=exam.status,
        created_at=exam.created_at,
        completed_at=exam.completed_at,
        document_count=doc_count,
        student_count=student_count,
        graded_count=graded_count,
        average_percentage=float(avg_result) if avg_result else None
    )


@router.put("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    exam_data: ExamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update exam details."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    if exam_data.name is not None:
        exam.name = exam_data.name
    if exam_data.status is not None:
        exam.status = exam_data.status
    
    db.commit()
    db.refresh(exam)
    return exam


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an exam and all associated data."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    db.delete(exam)
    db.commit()
    return None
