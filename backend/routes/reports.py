from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from io import BytesIO
from pathlib import Path
import sys
import os
from pypdf import PdfReader, PdfWriter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.question import Question
from models.student_answer import StudentAnswer
from models.document import Document
from models.grade import Grade
from utils.auth import get_current_user
from services.report_service import report_service
from services.grading_report_bundle import build_excel_bytes, build_all_pdfs_zip_bytes

router = APIRouter()

def _display_student_name(raw_name: str | None) -> str:
    """Return display-safe name without file extension."""
    n = (raw_name or "").strip()
    if not n:
        return "Unknown"
    return Path(n).stem or n


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

    excel_bytes, filename = build_excel_bytes(db, exam)

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
    """Download PDF report for a specific student, with original paper appended."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    student_doc = db.query(Document).filter(
        Document.id == document_id,
        Document.exam_id == exam_id,
        Document.doc_type == "student_answer"
    ).first()
    if not student_doc:
        raise HTTPException(status_code=404, detail="Student grades not found")
    
    # Get grades
    grades = db.query(Grade).join(StudentAnswer).filter(
        StudentAnswer.document_id == document_id
    ).all()
    
    grade_list = []
    for g in grades:
        sa = g.student_answer
        q = sa.question if sa else None
        mg = q
        grade_list.append({
            "question_number": q.question_number if q else "",
            "question_text": (q.question_text if q else None) or "",
            "score": float(g.score or 0),
            "max_marks": float(g.max_marks or 0),
            "confidence": float(g.confidence) if g.confidence is not None else None,
            "student_answer": (sa.answer_text if sa else None) or "",
            "feedback": g.feedback or ""
        })
    
    total_score, total_max = db.query(
        func.coalesce(func.sum(Grade.score), 0),
        func.coalesce(func.sum(Grade.max_marks), 0)
    ).join(StudentAnswer).filter(
        StudentAnswer.document_id == document_id
    ).first() or (0, 0)
    total_score = float(total_score or 0)
    total_max = float(total_max or 0)
    percentage = (total_score / total_max * 100) if total_max > 0 else 0.0

    display_name = _display_student_name(student_doc.file_name)
    summary_pdf_bytes = report_service.generate_student_pdf(
        exam_name=exam.name,
        student_name=display_name,
        grades=grade_list,
        total_score=total_score,
        total_max=total_max,
        percentage=percentage
    )

    # Append student's original uploaded paper to the end of the report.
    merged = PdfWriter()
    summary_reader = PdfReader(BytesIO(summary_pdf_bytes))
    for page in summary_reader.pages:
        merged.add_page(page)

    try:
        original_reader = PdfReader(student_doc.file_path)
        for page in original_reader.pages:
            merged.add_page(page)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append original paper PDF: {str(e)}")

    merged_buffer = BytesIO()
    merged.write(merged_buffer)
    merged_pdf_bytes = merged_buffer.getvalue()
    
    filename = f"{display_name}_report.pdf"
    
    return Response(
        content=merged_pdf_bytes,
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
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    zipped = build_all_pdfs_zip_bytes(db, exam)
    if not zipped:
        raise HTTPException(status_code=404, detail="No graded students found")

    zip_bytes, zip_filename = zipped

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )
