from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import asyncio
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.extracted_text import ExtractedText
from models.question import Question
from models.student_answer import StudentAnswer
from models.grade import Grade
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
from config import smtp_configured
from services.email_service import send_grading_complete_email
from services.grading_report_bundle_service import build_excel_bytes, build_all_pdfs_zip_bytes

router = APIRouter()


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _quote_grounded(quote: str, student_answer: str) -> bool:
    q = _norm_ws(quote)
    sa = _norm_ws(student_answer)
    return bool(q) and (q in sa)


def _student_totals(db: Session, document_id: str) -> tuple[float, float, float]:
    score_sum, max_sum = db.query(
        func.coalesce(func.sum(Grade.score), 0),
        func.coalesce(func.sum(Grade.max_marks), 0),
    ).join(StudentAnswer).filter(
        StudentAnswer.document_id == document_id
    ).first() or (0, 0)
    total_score = float(score_sum or 0)
    total_max = float(max_sum or 0)
    pct = (total_score / total_max * 100) if total_max > 0 else 0.0
    return total_score, total_max, pct


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
    
    guide_count = db.query(Question).filter(Question.exam_id == exam_id).count()
    if guide_count == 0:
        raise HTTPException(status_code=400, detail="No marking guide. Generate it first.")
    
    # Count student papers
    student_docs = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "student_answer"
    ).all()
    
    if not student_docs:
        raise HTTPException(status_code=400, detail="No student answer sheets uploaded.")
    
    provider = (request.provider or "ollama").strip().lower()
    if provider not in {"ollama", "openrouter"}:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'ollama' or 'openrouter'.")
    model = (request.model or "").strip() or None
    if provider == "ollama":
        # Local Ollama: model comes only from OLLAMA_MODEL env — never from the client.
        model = None

    # Update exam status
    exam.status = "grading"
    db.commit()
    
    # Start background grading
    background_tasks.add_task(grade_exam_background, exam_id, provider, model)
    
    return StartGradingResponse(
        exam_id=exam_id,
        status="grading",
        message="Grading started in background",
        students_to_grade=len(student_docs),
        provider=provider,
        model=model
    )


async def grade_exam_background(exam_id: str, provider: str = "ollama", model: str = None):
    from database import SessionLocal
    db = SessionLocal()

    if (provider or "").strip().lower() == "ollama":
        model = None

    email_payload: Optional[Tuple] = None

    try:
        # Get marking guide
        guides = db.query(Question).filter(
            Question.exam_id == exam_id
        ).order_by(Question.question_number).all()

        # Get student documents
        student_docs = db.query(Document).filter(
            Document.exam_id == exam_id,
            Document.doc_type == "student_answer"
        ).all()

        for doc in student_docs:
            try:
                await grade_student_paper(db, doc, guides, exam_id, provider=provider, model=model)
            except Exception as e:
                print(f"Error grading document {doc.id}: {e}")

        # Update exam status
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if exam:
            exam.status = "completed"
            exam.completed_at = datetime.utcnow()
            db.commit()

            if smtp_configured():
                owner = db.query(User).filter(User.id == exam.user_id).first()
                if owner and owner.email:
                    try:
                        excel_b, x_fn = build_excel_bytes(db, exam)
                        z_pair = build_all_pdfs_zip_bytes(db, exam)
                        z_b, z_fn = z_pair if z_pair else (None, None)
                        display_name = (owner.name or "").strip() or None
                        email_payload = (
                            owner.email,
                            display_name,
                            exam.name,
                            exam.id,
                            excel_b,
                            x_fn,
                            z_b,
                            z_fn,
                        )
                        print(
                            f"[grading-email] prepared for exam_id={exam.id} → {owner.email}",
                            flush=True,
                        )
                    except Exception as e2:
                        print(f"[grading-email] attachment build failed: {e2}", flush=True)
                else:
                    print(
                        "[grading-email] skipped: user account has no email (register with a real address)",
                        flush=True,
                    )
            else:
                print(
                    "[grading-email] skipped: SMTP not configured "
                    "(set SMTP_USER + SMTP_PASSWORD in .env at project root or backend/)",
                    flush=True,
                )

    except Exception as e:
        print(f"Error in grading background task: {e}")
    finally:
        db.close()

    if email_payload:
        try:
            await asyncio.to_thread(send_grading_complete_email, *email_payload)
            print("[grading-email] sent OK", flush=True)
        except Exception as e:
            print(f"[grading-email] send failed: {e}", flush=True)
            import traceback
            traceback.print_exc()


async def grade_student_paper(
    db: Session,
    doc: Document,
    guides: List[Question],
    exam_id: str,
    provider: str = "ollama",
    model: str = None
):

    # Before grading, remove any previous results for this student document so
    # re-running grading replaces the old results instead of duplicating them.
    old_student_answers = db.query(StudentAnswer).filter(
        StudentAnswer.document_id == doc.id
    ).all()
    old_answer_ids = [sa.id for sa in old_student_answers]

    if old_answer_ids:
        db.query(Grade).filter(
            Grade.student_answer_id.in_(old_answer_ids)
        ).delete(synchronize_session=False)
        db.query(StudentAnswer).filter(
            StudentAnswer.id.in_(old_answer_ids)
        ).delete(synchronize_session=False)

    db.commit()

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
    
    # Combine all extracted text (fallback if we can't find per-question regions)
    full_text = "\n".join([t.raw_text or "" for t in existing_text])

    # Build lookup of cropped answer regions by question_number for this student doc.
    # This lets us grade per cropped answer instead of whole-paper text.
    answer_regions = db.query(ExtractedText).filter(
        ExtractedText.document_id == doc.id,
        ExtractedText.region_type == "student_answer",
        ExtractedText.question_number.isnot(None)
    ).all()
    regions_by_qnum: dict[str, list[ExtractedText]] = {}
    for r in answer_regions:
        qnum = (r.question_number or "").strip()
        if not qnum:
            continue
        regions_by_qnum.setdefault(qnum, []).append(r)

    # Use LLM to map answers to questions and grade
    total_score = Decimal(0)
    total_max = Decimal(0)
    
    for guide in guides:
        try:
            # Grade this question
            # Prefer the text from the student's cropped region(s) that match this question number.
            qobj = guide
            qnum = ((qobj.question_number if qobj else None) or "").strip()
            matched_regions = regions_by_qnum.get(qnum) if qnum else None
            if matched_regions:
                student_answer_text = "\n".join([r.raw_text or "" for r in matched_regions])
                extracted_ref_id = matched_regions[0].id
            else:
                # Fallback: use combined text from entire paper
                student_answer_text = full_text
                extracted_ref_id = None

            result = await llm_service.grade_answer(
                question=(qobj.question_text if qobj else "") or "",
                answer_scheme=guide.answer_scheme or "",
                student_answer=student_answer_text,
                max_marks=float(guide.max_marks or 0),
                provider=provider,
                model_override=model
            )

            # Parse / normalize score from the LLM response
            parsed = result.parsed_response
            if not isinstance(parsed, dict) or "score" not in parsed:
                # If the model didn't return valid JSON, try to extract a score/feedback
                # from natural-language responses like "Score: 2.5/3.0" and "Feedback: ...".
                raw = result.raw_response or ""
                score_val = None
                feedback_val = ""
                confidence_val = None

                # Look for "Score: 2.5/3.0" or "SCORE: 1.5"
                # e.g. "**Score:** 2.5/3.0" or "SCORE: 1.5"
                m_score = re.search(r"(?i)score\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", raw)
                if m_score:
                    try:
                        score_val = float(m_score.group(1))
                    except Exception:
                        score_val = None

                # Look for "Confidence: 0.82" or "confidence=82%"
                m_conf = re.search(r"(?i)confidence\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*%?", raw)
                if m_conf:
                    try:
                        conf_num = float(m_conf.group(1))
                        confidence_val = conf_num / 100.0 if conf_num > 1.0 else conf_num
                    except Exception:
                        confidence_val = None

                # Look for "Feedback: ..." (fallback only; JSON path preferred)
                m_fb = re.search(r"(?is)feedback\s*[:=]\s*(.+)$", raw)
                if m_fb:
                    feedback_val = (m_fb.group(1) or "").strip()

                if score_val is not None:
                    # Round to nearest whole number and clamp to [0, max_marks]
                    rounded = round(score_val)
                    max_m = float(guide.max_marks or 0)
                    if max_m > 0:
                        rounded = max(0.0, min(max_m, rounded))
                    parsed = {
                        "score": rounded,
                        "confidence": confidence_val,
                        "feedback": feedback_val
                    }
                else:
                    # If we still can't parse, log a warning with a truncated preview
                    try:
                        preview = raw[:400]
                        print(
                            f"[LLM grading warning] Could not parse JSON/score for "
                            f"question {qnum!r}: raw_response preview={preview!r}"
                        )
                    except Exception:
                        pass
                    parsed = parsed or {}

            if not isinstance(parsed, dict):
                parsed = {}
            # Lexical confidence from completion logprobs (geometric mean of token probs); overrides regex "Confidence:" when present.
            if result.confidence_from_logprobs is not None:
                parsed["confidence"] = result.confidence_from_logprobs

            # Quote-grounding guardrail: if the model provided evidence_quotes,
            # ensure at least one quote is grounded in the student answer. If not,
            # force score=0 with low confidence to avoid hallucinated grading.
            try:
                quotes = parsed.get("evidence_quotes")
                if isinstance(quotes, list):
                    grounded_any = any(
                        isinstance(q, str) and _quote_grounded(q, student_answer_text or "")
                        for q in quotes
                    )
                    if not grounded_any:
                        parsed["score"] = 0
                        parsed["confidence"] = 0.0
                        parsed["feedback"] = "No relevant evidence found in the student's answer for the marking scheme."
            except Exception:
                pass

            score = Decimal(str(parsed.get("score", 0)))
            max_marks = Decimal(str(guide.max_marks or 0))

            # Only now that we have a valid score do we persist the related records
            llm_resp = LLMResponse(
                exam_id=exam_id,
                request_type="grading",
                input_text=f"Q: {(qobj.question_text if qobj else '')}\nStudent: {student_answer_text[:1000]}",
                prompt_used="grade_answer",
                raw_response=result.raw_response,
                parsed_response=parsed,
                model_used=f"{provider}:{result.model_used}",
                processing_time_ms=result.processing_time_ms,
                tokens_used=result.tokens_used,
            )
            db.add(llm_resp)

            student_ans = StudentAnswer(
                document_id=doc.id,
                question_id=guide.id,
                extracted_text_id=extracted_ref_id,
                # Store truncated student answer text for display in UI
                answer_text=student_answer_text[:1000] if student_answer_text else None
            )
            db.add(student_ans)

            conf = parsed.get("confidence")
            grade = Grade(
                student_answer=student_ans,
                llm_response=llm_resp,
                score=score,
                max_marks=max_marks,
                confidence=Decimal(str(conf)) if conf is not None else None,
                feedback=parsed.get("feedback", "")
            )
            db.add(grade)

            total_score += score
            total_max += max_marks
            
        except Exception as e:
            print(f"Error grading question {qnum}: {e}")

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
    
    student_docs = db.query(Document).filter(
        Document.exam_id == exam_id,
        Document.doc_type == "student_answer"
    ).all()

    students = []
    for doc in student_docs:
        grades = db.query(Grade).join(StudentAnswer).filter(
            StudentAnswer.document_id == doc.id
        ).all()
        
        grade_details = []
        for g in grades:
            sa = g.student_answer
            q = sa.question if sa else None
            mg = q
            
            grade_details.append(StudentGradeDetail(
                id=str(g.id),
                question_number=q.question_number if q else "",
                question_text=q.question_text if q else "",
                answer_scheme=mg.answer_scheme if mg else "",
                student_answer=sa.answer_text[:200] if sa and sa.answer_text else "",
                score=float(g.score) if g.score is not None else None,
                max_marks=float(g.max_marks) if g.max_marks is not None else None,
                confidence=float(g.confidence) if g.confidence is not None else None,
                feedback=g.feedback,
                is_overridden=g.is_overridden
            ))
        
        total_score, total_max, pct = _student_totals(db, doc.id)
        students.append(StudentGradeSummary(
            document_id=doc.id,
            student_name=doc.file_name,
            total_score=total_score,
            total_max_marks=total_max,
            percentage=pct,
            grades=grade_details
        ))
    avg_pct = (sum(s.percentage for s in students) / len(students)) if students else None

    return ExamGradingSummary(
        exam_id=exam_id,
        exam_name=exam.name,
        status=exam.status,
        total_students=len(student_docs),
        graded_students=len(students),
        average_percentage=float(avg_pct) if avg_pct is not None else None,
        students=students
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

    if grade.max_marks is not None and Decimal(str(update.score)) > grade.max_marks:
        raise HTTPException(status_code=400, detail="Score cannot exceed max marks")
    
    # Store original if not already overridden
    if not grade.is_overridden:
        grade.original_score = grade.score
    
    grade.score = Decimal(str(update.score))
    if update.feedback is not None:
        grade.feedback = update.feedback
    grade.is_overridden = True
    grade.overridden_at = datetime.utcnow()
    
    db.commit()
    
    db.refresh(grade)
    return grade
