"""Build Excel + PDF zip payloads for an exam (shared by HTTP routes and grading emails)."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from pypdf import PdfReader, PdfWriter
from models.document import Document
from models.exam import Exam
from models.grade import Grade, GradingSummary
from models.marking_guide import MarkingGuide
from models.student_answer import StudentAnswer
from services.report_service import report_service

def _display_student_name(raw_name: str | None) -> str:
    n = (raw_name or "").strip()
    if not n:
        return "Unknown"
    return Path(n).stem or n


def load_grade_report_context(
    db: Session, exam: Exam
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[GradingSummary]]:
    guides = (
        db.query(MarkingGuide)
        .filter(MarkingGuide.exam_id == exam.id)
        .order_by(MarkingGuide.question_number)
        .all()
    )
    questions = [
        {"question_number": g.question_number, "max_marks": float(g.max_marks or 0)}
        for g in guides
    ]

    summaries = (
        db.query(GradingSummary).filter(GradingSummary.exam_id == exam.id).all()
    )

    students: List[Dict[str, Any]] = []
    for summary in summaries:
        grades = (
            db.query(Grade)
            .join(StudentAnswer)
            .filter(StudentAnswer.document_id == summary.document_id)
            .all()
        )
        grade_list = []
        for g in grades:
            mg = g.student_answer.marking_guide if g.student_answer else None
            grade_list.append(
                {
                    "question_number": mg.question_number if mg else "",
                    "score": float(g.score or 0),
                }
            )
        students.append(
            {
                "student_name": summary.student_name or "Unknown",
                "total_score": float(summary.total_score or 0),
                "percentage": float(summary.percentage or 0),
                "grades": grade_list,
            }
        )

    return questions, students, summaries


def build_excel_bytes(db: Session, exam: Exam) -> Tuple[bytes, str]:
    questions, students, _ = load_grade_report_context(db, exam)
    excel_bytes = report_service.generate_excel_summary(
        exam_name=exam.name,
        students=students,
        questions=questions,
    )
    filename = f"{exam.name.replace(' ', '_')}_grades.xlsx"
    return excel_bytes, filename


def build_all_pdfs_zip_bytes(db: Session, exam: Exam) -> Optional[Tuple[bytes, str]]:
    _, _, summaries = load_grade_report_context(db, exam)
    if not summaries:
        return None

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for summary in summaries:
            grades = (
                db.query(Grade)
                .join(StudentAnswer)
                .filter(StudentAnswer.document_id == summary.document_id)
                .all()
            )
            grade_list = []
            for g in grades:
                mg = g.student_answer.marking_guide if g.student_answer else None
                sa = g.student_answer
                grade_list.append(
                    {
                        "question_number": mg.question_number if mg else "",
                        "question_text": (mg.question_text if mg else None) or "",
                        "score": float(g.score or 0),
                        "max_marks": float(g.max_marks or 0),
                        "confidence": float(g.confidence) if g.confidence is not None else None,
                        "student_answer": (sa.answer_text if sa else None) or "",
                        "feedback": g.feedback or "",
                    }
                )

            pdf_bytes = report_service.generate_student_pdf(
                exam_name=exam.name,
                student_name=_display_student_name(summary.student_name),
                grades=grade_list,
                total_score=float(summary.total_score or 0),
                total_max=float(summary.total_max_marks or 0),
                percentage=float(summary.percentage or 0),
            )
            # Append student's original answer sheet at the back of the summary report.
            merged = PdfWriter()
            summary_reader = PdfReader(BytesIO(pdf_bytes))
            for p in summary_reader.pages:
                merged.add_page(p)

            student_doc = (
                db.query(Document)
                .filter(
                    Document.id == summary.document_id,
                    Document.exam_id == exam.id,
                    Document.doc_type == "student_answer",
                )
                .first()
            )
            if student_doc and student_doc.file_path:
                try:
                    original_reader = PdfReader(student_doc.file_path)
                    for p in original_reader.pages:
                        merged.add_page(p)
                except Exception:
                    # Keep summary pages even if original paper is unreadable.
                    pass

            out = BytesIO()
            merged.write(out)
            fname = f"{_display_student_name(summary.student_name) or 'student'}_{summary.document_id[:8]}.pdf"
            zip_file.writestr(fname, out.getvalue())

    zip_buffer.seek(0)
    zip_name = f"{exam.name.replace(' ', '_')}_all_reports.zip"
    return zip_buffer.getvalue(), zip_name
