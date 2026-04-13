from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from io import BytesIO
from pathlib import Path
import sys
import os
from pypdf import PdfReader, PdfWriter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.marking_guide import MarkingGuide
from models.student_answer import StudentAnswer
from models.document import Document
from models.grade import Grade, GradingSummary
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
        sa = g.student_answer
        grade_list.append({
            "question_number": mg.question_number if mg else "",
            "question_text": (mg.question_text if mg else None) or "",
            "score": float(g.score or 0),
            "max_marks": float(g.max_marks or 0),
            "confidence": float(g.confidence) if g.confidence is not None else None,
            "student_answer": (sa.answer_text if sa else None) or "",
            "feedback": g.feedback or ""
        })
    
    # Generate PDF
    display_name = _display_student_name(summary.student_name)
    summary_pdf_bytes = report_service.generate_student_pdf(
        exam_name=exam.name,
        student_name=display_name,
        grades=grade_list,
        total_score=float(summary.total_score or 0),
        total_max=float(summary.total_max_marks or 0),
        percentage=float(summary.percentage or 0)
    )

    # Append student's original uploaded paper to the end of the report.
    student_doc = db.query(Document).filter(
        Document.id == document_id,
        Document.exam_id == exam_id,
        Document.doc_type == "student_answer"
    ).first()

    if not student_doc:
        raise HTTPException(status_code=404, detail="Student answer document not found")

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
