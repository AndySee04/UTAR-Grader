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
from models.grade import Grade
from models.question import Question
from models.student_answer import StudentAnswer
from services.report_service import report_service


def _display_student_name(raw_name: str | None) -> str:
    n = (raw_name or "").strip()
    if not n:
        return "Unknown"
    return Path(n).stem or n


def load_grade_report_context(
    db: Session, exam: Exam
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Document]]:
    guides = db.query(Question).filter(
        Question.exam_id == exam.id
    ).order_by(Question.question_number).all()
    questions = []
    for g in guides:
        questions.append({
            "question_number": (g.question_number or ""),
            "max_marks": float(g.max_marks or 0),
        })

    docs = db.query(Document).filter(
        Document.exam_id == exam.id,
        Document.doc_type == "student_answer"
    ).all()

    students: List[Dict[str, Any]] = []
    for doc in docs:
        grades = (
            db.query(Grade)
            .join(StudentAnswer)
            .filter(StudentAnswer.document_id == doc.id)
            .all()
        )
        grade_list = []
        for g in grades:
            q = g.student_answer.question if g.student_answer else None
            grade_list.append(
                {
                    "question_number": q.question_number if q else "",
                    "score": float(g.score or 0),
                }
            )
        students.append(
            {
                "student_name": doc.file_name or "Unknown",
                "total_score": float(sum(float(g.score or 0) for g in grades)),
                "percentage": (
                    (float(sum(float(g.score or 0) for g in grades)) / float(sum(float(g.max_marks or 0) for g in grades)) * 100)
                    if float(sum(float(g.max_marks or 0) for g in grades)) > 0 else 0.0
                ),
                "grades": grade_list,
            }
        )

    return questions, students, docs


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
    _, _, docs = load_grade_report_context(db, exam)
    if not docs:
        return None

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for doc in docs:
            grades = (
                db.query(Grade)
                .join(StudentAnswer)
                .filter(StudentAnswer.document_id == doc.id)
                .all()
            )
            grade_list = []
            for g in grades:
                sa = g.student_answer
                q = sa.question if sa else None
                grade_list.append(
                    {
                        "question_number": q.question_number if q else "",
                        "question_text": (q.question_text if q else None) or "",
                        "score": float(g.score or 0),
                        "max_marks": float(g.max_marks or 0),
                        "confidence": float(g.confidence) if g.confidence is not None else None,
                        "student_answer": (sa.answer_text if sa else None) or "",
                        "feedback": g.feedback or "",
                    }
                )

            pdf_bytes = report_service.generate_student_pdf(
                exam_name=exam.name,
                student_name=_display_student_name(doc.file_name),
                grades=grade_list,
                total_score=float(sum(float(g.score or 0) for g in grades)),
                total_max=float(sum(float(g.max_marks or 0) for g in grades)),
                percentage=(
                    (float(sum(float(g.score or 0) for g in grades)) / float(sum(float(g.max_marks or 0) for g in grades)) * 100)
                    if float(sum(float(g.max_marks or 0) for g in grades)) > 0 else 0.0
                ),
            )
            # Append student's original answer sheet at the back of the summary report.
            merged = PdfWriter()
            summary_reader = PdfReader(BytesIO(pdf_bytes))
            for p in summary_reader.pages:
                merged.add_page(p)

            student_doc = (
                db.query(Document)
                .filter(
                    Document.id == doc.id,
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
            fname = f"{_display_student_name(doc.file_name) or 'student'}_{doc.id[:8]}.pdf"
            zip_file.writestr(fname, out.getvalue())

    zip_buffer.seek(0)
    zip_name = f"{exam.name.replace(' ', '_')}_all_reports.zip"
    return zip_buffer.getvalue(), zip_name
