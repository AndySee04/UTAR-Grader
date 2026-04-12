"""Build Excel + PDF zip payloads for an exam (shared by HTTP routes and grading emails)."""

from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models.exam import Exam
from models.grade import Grade, GradingSummary
from models.marking_guide import MarkingGuide
from models.student_answer import StudentAnswer
from services.report_service import report_service


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
                student_name=summary.student_name or "Unknown",
                grades=grade_list,
                total_score=float(summary.total_score or 0),
                total_max=float(summary.total_max_marks or 0),
                percentage=float(summary.percentage or 0),
            )
            fname = f"{summary.student_name or 'student'}_{summary.document_id[:8]}.pdf"
            zip_file.writestr(fname, pdf_bytes)

    zip_buffer.seek(0)
    zip_name = f"{exam.name.replace(' ', '_')}_all_reports.zip"
    return zip_buffer.getvalue(), zip_name
