from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.extracted_text import ExtractedText
from models.marking_guide import MarkingGuide
from models.student_answer import StudentAnswer
from models.grade import Grade, GradingSummary
from models.llm_response import LLMResponse
from schemas.grade import (
    GradeResponse, GradeUpdate, StudentGradeDetail,
    StudentGradeSummary, ExamGradingSummary,
    StartGradingRequest, StartGradingResponse
)
from utils.auth import get_current_user
from services.llm_service import llm_service
from services.pdf_service import pdf_service
from services.ocr_service import ocr_service
from services.cv_service import cv_service

router = APIRouter()


@router.post("/exams/{exam_id}/grade", response_model=StartGradingResponse)
async def start_grading(
    exam_id: str,
    request: StartGradingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start grading all student papers for an exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Check marking guide exists
    guide_count = db.query(MarkingGuide).filter(MarkingGuide.exam_id == exam_id).count()
    if guide_count == 0:
        raise HTTPException(status_code=400, detail="No marking guide. Generate it first.")
    
    # Count student papers
    student_docs = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "student_answer"
    ).all()
    
    if not student_docs:
        raise HTTPException(status_code=400, detail="No student answer sheets uploaded.")
    
    # Update exam status
    exam.status = "grading"
    db.commit()
    
    # Start background grading
    background_tasks.add_task(grade_exam_background, exam_id)
    
    return StartGradingResponse(
        exam_id=exam_id,
        status="grading",
        message="Grading started in background",
        students_to_grade=len(student_docs)
    )


async def grade_exam_background(exam_id: str):
    """Background task to grade all student papers."""
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        # Get marking guide
        guides = db.query(MarkingGuide).filter(
            MarkingGuide.exam_id == exam_id
        ).order_by(MarkingGuide.question_number).all()
        
        # Get student documents
        student_docs = db.query(Document).filter(
            Document.exam_id == exam_id,
            Document.doc_type == "student_answer"
        ).all()
        
        for doc in student_docs:
            try:
                await grade_student_paper(db, doc, guides, exam_id)
            except Exception as e:
                print(f"Error grading document {doc.id}: {e}")
        
        # Update exam status
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if exam:
            exam.status = "completed"
            exam.completed_at = datetime.utcnow()
            db.commit()
    
    except Exception as e:
        print(f"Error in grading background task: {e}")
    finally:
        db.close()


async def grade_student_paper(db: Session, doc: Document, guides: List[MarkingGuide], exam_id: str):
    """Grade a single student's paper."""
    # First, extract text from student paper if not already done
    existing_text = db.query(ExtractedText).filter(
        ExtractedText.document_id == doc.id
    ).all()
    
    if not existing_text:
        # Process student paper
        for pg in range(1, (doc.page_count or 1) + 1):
            try:
                img = pdf_service.get_page_as_image(doc.file_path, pg)
                text, _ = ocr_service.extract_text_from_image(img)
                
                extracted = ExtractedText(
                    document_id=doc.id,
                    page_number=pg,
                    region_type="student_answer",
                    raw_text=text
                )
                db.add(extracted)
            except:
                pass
        db.commit()
        existing_text = db.query(ExtractedText).filter(
            ExtractedText.document_id == doc.id
        ).all()
    
    # Combine all extracted text
    full_text = "\n".join([t.raw_text or "" for t in existing_text])
    
    # Use LLM to map answers to questions and grade
    total_score = Decimal(0)
    total_max = Decimal(0)
    
    for guide in guides:
        try:
            # Grade this question
            result = await llm_service.grade_answer(
                question=guide.question_text or "",
                answer_scheme=guide.answer_scheme or "",
                student_answer=full_text,  # LLM will find relevant part
                max_marks=float(guide.max_marks or 0)
            )
            
            # Save LLM response
            llm_resp = LLMResponse(
                exam_id=exam_id,
                request_type="grading",
                input_text=f"Q: {guide.question_text}\nStudent: {full_text[:500]}",
                raw_response=result.raw_response,
                parsed_response=result.parsed_response,
                model_used=result.model_used,
                processing_time_ms=result.processing_time_ms
            )
            db.add(llm_resp)
            db.flush()
            
            # Create student answer record
            student_ans = StudentAnswer(
                document_id=doc.id,
                marking_guide_id=guide.id,
                answer_text=full_text[:1000]  # Store truncated
            )
            db.add(student_ans)
            db.flush()
            
            # Create grade record
            parsed = result.parsed_response or {}
            score = Decimal(str(parsed.get("score", 0)))
            max_marks = Decimal(str(guide.max_marks or 0))
            
            grade = Grade(
                student_answer_id=student_ans.id,
                llm_response_id=llm_resp.id,
                score=score,
                max_marks=max_marks,
                feedback=parsed.get("feedback", "")
            )
            db.add(grade)
            
            total_score += score
            total_max += max_marks
            
        except Exception as e:
            print(f"Error grading question {guide.question_number}: {e}")
    
    # Create summary
    percentage = (total_score / total_max * 100) if total_max > 0 else Decimal(0)
    
    summary = GradingSummary(
        exam_id=exam_id,
        document_id=doc.id,
        student_name=doc.student_name,
        total_score=total_score,
        total_max_marks=total_max,
        percentage=percentage
    )
    db.add(summary)
    db.commit()


@router.get("/exams/{exam_id}/grades", response_model=ExamGradingSummary)
async def get_exam_grades(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all grades for an exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get summaries
    summaries = db.query(GradingSummary).filter(
        GradingSummary.exam_id == exam_id
    ).all()
    
    # Get total students
    total_students = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "student_answer"
    ).count()
    
    # Calculate average
    avg_pct = db.query(func.avg(GradingSummary.percentage)).filter(
        GradingSummary.exam_id == exam_id
    ).scalar()
    
    students = []
    for summary in summaries:
        # Get detailed grades for this student
        grades = db.query(Grade).join(StudentAnswer).filter(
            StudentAnswer.document_id == summary.document_id
        ).all()
        
        grade_details = []
        for g in grades:
            sa = g.student_answer
            mg = sa.marking_guide if sa else None
            
            grade_details.append(StudentGradeDetail(
                question_number=mg.question_number if mg else "",
                question_text=mg.question_text if mg else "",
                student_answer=sa.answer_text[:200] if sa and sa.answer_text else "",
                score=float(g.score) if g.score else None,
                max_marks=float(g.max_marks) if g.max_marks else None,
                feedback=g.feedback,
                is_overridden=g.is_overridden
            ))
        
        students.append(StudentGradeSummary(
            document_id=summary.document_id,
            student_name=summary.student_name,
            total_score=float(summary.total_score or 0),
            total_max_marks=float(summary.total_max_marks or 0),
            percentage=float(summary.percentage or 0),
            grades=grade_details
        ))
    
    return ExamGradingSummary(
        exam_id=exam_id,
        exam_name=exam.name,
        status=exam.status,
        total_students=total_students,
        graded_students=len(summaries),
        average_percentage=float(avg_pct) if avg_pct else None,
        students=students
    )


@router.get("/exams/{exam_id}/grades/{document_id}", response_model=StudentGradeSummary)
async def get_student_grades(
    exam_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get grades for a specific student."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    summary = db.query(GradingSummary).filter(
        GradingSummary.exam_id == exam_id,
        GradingSummary.document_id == document_id
    ).first()
    
    if not summary:
        raise HTTPException(status_code=404, detail="Student grades not found")
    
    grades = db.query(Grade).join(StudentAnswer).filter(
        StudentAnswer.document_id == document_id
    ).all()
    
    grade_details = []
    for g in grades:
        sa = g.student_answer
        mg = sa.marking_guide if sa else None
        
        grade_details.append(StudentGradeDetail(
            question_number=mg.question_number if mg else "",
            question_text=mg.question_text if mg else "",
            student_answer=sa.answer_text if sa else "",
            score=float(g.score) if g.score else None,
            max_marks=float(g.max_marks) if g.max_marks else None,
            feedback=g.feedback,
            is_overridden=g.is_overridden
        ))
    
    return StudentGradeSummary(
        document_id=document_id,
        student_name=summary.student_name,
        total_score=float(summary.total_score or 0),
        total_max_marks=float(summary.total_max_marks or 0),
        percentage=float(summary.percentage or 0),
        grades=grade_details
    )


@router.put("/grades/{grade_id}", response_model=GradeResponse)
async def override_grade(
    grade_id: str,
    update: GradeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Override a grade (teacher correction)."""
    grade = db.query(Grade).join(StudentAnswer).join(Document).join(Exam).filter(
        Grade.id == grade_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    
    # Store original if not already overridden
    if not grade.is_overridden:
        grade.original_score = grade.score
    
    grade.score = Decimal(str(update.score))
    if update.feedback is not None:
        grade.feedback = update.feedback
    grade.is_overridden = True
    grade.overridden_at = datetime.utcnow()
    
    db.commit()
    
    # Update summary
    student_answer = grade.student_answer
    if student_answer:
        summary = db.query(GradingSummary).filter(
            GradingSummary.document_id == student_answer.document_id
        ).first()
        
        if summary:
            # Recalculate totals
            all_grades = db.query(Grade).join(StudentAnswer).filter(
                StudentAnswer.document_id == student_answer.document_id
            ).all()
            
            total_score = sum(Decimal(str(g.score or 0)) for g in all_grades)
            total_max = sum(Decimal(str(g.max_marks or 0)) for g in all_grades)
            
            summary.total_score = total_score
            summary.percentage = (total_score / total_max * 100) if total_max > 0 else Decimal(0)
            db.commit()
    
    db.refresh(grade)
    return grade


@router.get("/exams/{exam_id}/progress")
async def get_grading_progress(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get grading progress for an exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    total = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "student_answer"
    ).count()
    
    graded = db.query(GradingSummary).filter(
        GradingSummary.exam_id == exam_id
    ).count()
    
    return {
        "exam_id": exam_id,
        "status": exam.status,
        "total_students": total,
        "graded_students": graded,
        "progress_percentage": (graded / total * 100) if total > 0 else 0
    }
