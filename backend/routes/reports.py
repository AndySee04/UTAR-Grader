from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.marking_guide import MarkingGuide
from models.student_answer import StudentAnswer
from models.grade import Grade, GradingSummary
from utils.auth import get_current_user
from services.report_service import report_service

router = APIRouter()


@router.get("/exams/{exam_id}/report/excel")
async def download_excel_report(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download Excel summary report for an exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get questions
    guides = db.query(MarkingGuide).filter(
        MarkingGuide.exam_id == exam_id
    ).order_by(MarkingGuide.question_number).all()
    
    questions = [
        {
            "question_number": g.question_number,
            "max_marks": float(g.max_marks or 0)
        }
        for g in guides
    ]
    
    # Get student summaries
    summaries = db.query(GradingSummary).filter(
        GradingSummary.exam_id == exam_id
    ).all()
    
    students = []
    for summary in summaries:
        grades = db.query(Grade).join(StudentAnswer).filter(
            StudentAnswer.document_id == summary.document_id
        ).all()
        
        grade_list = []
        for g in grades:
            mg = g.student_answer.marking_guide if g.student_answer else None
            grade_list.append({
                "question_number": mg.question_number if mg else "",
                "score": float(g.score or 0)
            })
        
        students.append({
            "student_name": summary.student_name or "Unknown",
            "total_score": float(summary.total_score or 0),
            "percentage": float(summary.percentage or 0),
            "grades": grade_list
        })
    
    # Generate Excel
    excel_bytes = report_service.generate_excel_summary(
        exam_name=exam.name,
        students=students,
        questions=questions
    )
    
    filename = f"{exam.name.replace(' ', '_')}_grades.xlsx"
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/exams/{exam_id}/report/pdf/{document_id}")
async def download_student_pdf(
    exam_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download PDF report for a specific student."""
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
    
    # Get grades
    grades = db.query(Grade).join(StudentAnswer).filter(
        StudentAnswer.document_id == document_id
    ).all()
    
    grade_list = []
    for g in grades:
        mg = g.student_answer.marking_guide if g.student_answer else None
        grade_list.append({
            "question_number": mg.question_number if mg else "",
            "score": float(g.score or 0),
            "max_marks": float(g.max_marks or 0),
            "feedback": g.feedback or ""
        })
    
    # Generate PDF
    pdf_bytes = report_service.generate_student_pdf(
        exam_name=exam.name,
        student_name=summary.student_name or "Unknown",
        grades=grade_list,
        total_score=float(summary.total_score or 0),
        total_max=float(summary.total_max_marks or 0),
        percentage=float(summary.percentage or 0)
    )
    
    filename = f"{summary.student_name or 'student'}_report.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/exams/{exam_id}/report/all-pdfs")
async def download_all_student_pdfs(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download all student PDFs as a zip file."""
    import zipfile
    from io import BytesIO
    
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    summaries = db.query(GradingSummary).filter(
        GradingSummary.exam_id == exam_id
    ).all()
    
    if not summaries:
        raise HTTPException(status_code=404, detail="No graded students found")
    
    # Create zip file
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for summary in summaries:
            grades = db.query(Grade).join(StudentAnswer).filter(
                StudentAnswer.document_id == summary.document_id
            ).all()
            
            grade_list = []
            for g in grades:
                mg = g.student_answer.marking_guide if g.student_answer else None
                grade_list.append({
                    "question_number": mg.question_number if mg else "",
                    "score": float(g.score or 0),
                    "max_marks": float(g.max_marks or 0),
                    "feedback": g.feedback or ""
                })
            
            pdf_bytes = report_service.generate_student_pdf(
                exam_name=exam.name,
                student_name=summary.student_name or "Unknown",
                grades=grade_list,
                total_score=float(summary.total_score or 0),
                total_max=float(summary.total_max_marks or 0),
                percentage=float(summary.percentage or 0)
            )
            
            filename = f"{summary.student_name or 'student'}_{summary.document_id[:8]}.pdf"
            zip_file.writestr(filename, pdf_bytes)
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={exam.name}_all_reports.zip"}
    )
