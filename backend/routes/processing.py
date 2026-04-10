from fastapi import APIRouter, Depends, HTTPException, status, Body, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
import io
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.extracted_text import ExtractedText
from models.llm_response import LLMResponse
from utils.auth import get_current_user
from services.pdf_service import pdf_service
from services.cv_service import cv_service
from services.ocr_service import ocr_service, ocr_service_printed
from services.llm_service import llm_service

router = APIRouter()


@router.get("/documents/{document_id}/pages/{page_number}/image")
async def get_page_image(
    document_id: str,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific page as an image."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        img = pdf_service.get_page_as_image(document.file_path, page_number)
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get page image: {str(e)}")


@router.get("/documents/{document_id}/pages")
async def get_all_pages_info(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get information about all pages in a document."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    pages = []
    for i in range(1, (document.page_count or 0) + 1):
        try:
            width, height = pdf_service.get_page_dimensions(document.file_path, i)
            pages.append({
                "page_number": i,
                "width": width,
                "height": height,
                "image_url": f"/api/documents/{document_id}/pages/{i}/image"
            })
        except:
            pass
    
    return {"document_id": document_id, "page_count": document.page_count, "pages": pages}


@router.post("/documents/{document_id}/detect-regions")
async def detect_regions(
    document_id: str,
    page_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Auto-detect text regions in a document using computer vision."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    results = []
    pages_to_process = [page_number] if page_number else range(1, (document.page_count or 0) + 1)
    
    for pg in pages_to_process:
        try:
            img = pdf_service.get_page_as_image(document.file_path, pg)
            regions = cv_service.detect_text_regions(img)
            
            for idx, region in enumerate(regions):
                # Save to database
                extracted = ExtractedText(
                    document_id=document_id,
                    page_number=pg,
                    region_type=document.doc_type.replace("_paper", "").replace("_scheme", ""),
                    bounding_box={
                        "x": region.x,
                        "y": region.y,
                        "width": region.width,
                        "height": region.height
                    }
                )
                db.add(extracted)
                results.append({
                    "page_number": pg,
                    "region_index": idx,
                    "x": region.x,
                    "y": region.y,
                    "width": region.width,
                    "height": region.height
                })
        except Exception as e:
            results.append({"page_number": pg, "error": str(e)})
    
    db.commit()
    return {"document_id": document_id, "regions_detected": len(results), "regions": results}


@router.post("/regions/{region_id}/ocr")
async def run_ocr_on_region(
    region_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run OCR on a specific region."""
    region = db.query(ExtractedText).join(Document).join(Exam).filter(
        ExtractedText.id == region_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    
    document = region.document
    bbox = region.bounding_box or {}
    
    try:
        # Get page image
        img = pdf_service.get_page_as_image(document.file_path, region.page_number)
        
        # Crop region
        if bbox:
            # Safely read bounding box, and fall back to whole image if incomplete.
            x = bbox.get("x", 0) or 0
            y = bbox.get("y", 0) or 0
            w = bbox.get("width")
            h = bbox.get("height")

            if w is None or h is None:
                # If width/height are missing, treat as full page rather than
                # extending beyond the image.
                cropped = img
            else:
                left = max(0, int(x))
                top = max(0, int(y))
                right = min(img.width, left + int(w))
                bottom = min(img.height, top + int(h))
                if right <= left or bottom <= top:
                    # Degenerate box -> fall back to full image
                    cropped = img
                else:
                    cropped = img.crop((left, top, right, bottom))
        else:
            cropped = img
        
        # Run OCR - use printed-text model for question papers, handwriting model otherwise
        ocr = ocr_service_printed if document.doc_type == "question_paper" else ocr_service
        text, line_details = ocr.extract_text_from_image(cropped)
        heights = [
            (d.get("region", {}) or {}).get("height")
            for d in (line_details or [])
            if isinstance(d, dict)
        ]
        heights = [h for h in heights if isinstance(h, (int, float))]
        avg_line_height = (sum(heights) / len(heights)) if heights else 0.0
        print(
            "[OCR] "
            f"region_id={region.id} "
            f"doc_type={document.doc_type} "
            f"line_count={len(line_details)} "
            f"avg_line_height={avg_line_height:.2f}",
            flush=True
        )
        
        # Update region
        region.raw_text = text
        db.commit()
        
        return {
            "region_id": region_id,
            "raw_text": text,
            "line_count": len(line_details),
            "avg_line_height": avg_line_height
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")


@router.delete("/regions/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(
    region_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a region (extracted text) by id."""
    region = db.query(ExtractedText).join(Document).join(Exam).filter(
        ExtractedText.id == region_id,
        Exam.user_id == current_user.id
    ).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    db.delete(region)
    db.commit()
    return None


@router.patch("/regions/{region_id}")
async def update_region_text(
    region_id: str,
    body: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a region's raw_text (e.g. after user edit)."""
    region = db.query(ExtractedText).join(Document).join(Exam).filter(
        ExtractedText.id == region_id,
        Exam.user_id == current_user.id
    ).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    # Allow updating OCR text and optional metadata like question_number / marks
    if "raw_text" in body:
        region.raw_text = body["raw_text"]
        # Keep processed_text in sync with manual edits so regenerated
        # marking guides always reflect the latest teacher-corrected text.
        region.processed_text = body["raw_text"]
    synced_student_regions = 0
    if "question_number" in body:
        old_question_number = (region.question_number or "").strip()
        region.question_number = body["question_number"]
        # Optional sync: when question-paper numbering is changed manually,
        # propagate the label update to student-answer regions in the same exam.
        should_sync_students = bool(body.get("sync_student_regions"))
        new_question_number = (body.get("question_number") or "").strip()
        if (
            should_sync_students
            and region.document
            and region.document.doc_type == "question_paper"
            and old_question_number
            and new_question_number
            and old_question_number != new_question_number
        ):
            student_regions_all = (
                db.query(ExtractedText)
                .join(Document)
                .filter(
                    Document.exam_id == region.document.exam_id,
                    Document.doc_type == "student_answer",
                )
                .all()
            )

            old_norm = old_question_number.strip().lower()
            student_regions = [
                sr for sr in student_regions_all
                if (sr.question_number or "").strip().lower() == old_norm
            ]

            for sr in student_regions:
                sr.question_number = new_question_number
            synced_student_regions = len(student_regions)
    if "marks" in body:
        try:
            region.marks = float(body["marks"]) if body["marks"] is not None else None
        except (TypeError, ValueError):
            region.marks = None
    db.commit()
    db.refresh(region)
    return {
        "region_id": region_id,
        "raw_text": region.raw_text,
        "question_number": region.question_number,
        "marks": region.marks,
        "synced_student_regions": synced_student_regions,
    }


@router.post("/exams/{exam_id}/process")
async def process_exam_documents(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Process all documents for an exam (detect regions + OCR). Returns immediately."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Update status
    exam.status = "processing"
    db.commit()
    
    # Run in background so the API returns immediately.
    # We create a new DB session inside the background task.
    def _run_in_bg(exam_id_local: str):
        from database import SessionLocal
        bg_db = SessionLocal()
        try:
            process_exam_background(exam_id_local, bg_db)
        finally:
            bg_db.close()

    if background_tasks is not None:
        background_tasks.add_task(_run_in_bg, exam_id)
    else:
        # Fallback (should not happen): run synchronously
        _run_in_bg(exam_id)

    return {"message": "Processing started", "exam_id": exam_id, "status": "processing"}


def process_exam_background(exam_id: str, db: Session):
    """Background task to process exam documents."""
    try:
        documents = db.query(Document).filter(Document.exam_id == exam_id).all()
        to_process = [d for d in documents if d.doc_type != "student_answer"]
        total_docs = len(to_process)
        print(f"[Processing] Started exam {exam_id}: {total_docs} document(s) to process (question paper + answer scheme)", flush=True)
        for idx, doc in enumerate(to_process, 1):
            if doc.doc_type == "question_paper":
                existing = db.query(ExtractedText).filter(ExtractedText.document_id == doc.id).count()
                if existing > 0:
                    print(f"[Processing] Question paper already has regions, skipping.", flush=True)
                    continue
            print(f"[Processing] ({idx}/{total_docs}) {doc.doc_type}", flush=True)
            page_count = doc.page_count or 0
            for pg in range(1, page_count + 1):
                try:
                    print(f"[Processing]   Page {pg}/{page_count} — loading image...", flush=True)
                    img = pdf_service.get_page_as_image(doc.file_path, pg)
                    regions = cv_service.detect_text_regions(img)
                    print(f"[Processing]   Page {pg}/{page_count} — detected {len(regions)} region(s), running OCR...", flush=True)
                    for region in regions:
                        cropped = cv_service.crop_region(img, region)
                        # Use printed-text model for question paper pages, handwriting model for others
                        ocr = ocr_service_printed if doc.doc_type == "question_paper" else ocr_service
                        text, _ = ocr.extract_text_from_image(cropped)
                        extracted = ExtractedText(
                            document_id=doc.id,
                            page_number=pg,
                            region_type=doc.doc_type.replace("_paper", "").replace("_scheme", ""),
                            bounding_box={
                                "x": region.x,
                                "y": region.y,
                                "width": region.width,
                                "height": region.height
                            },
                            raw_text=text
                        )
                        db.add(extracted)
                except Exception as page_err:
                    print(f"[Processing]   Page {pg}/{page_count} — error: {page_err}", flush=True)
        db.commit()
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if exam:
            exam.status = "draft"
            db.commit()
        print(f"[Processing] Completed exam {exam_id}. Status set to draft.", flush=True)
    except Exception as e:
        print(f"[Processing] Error processing exam {exam_id}: {e}", flush=True)


@router.post("/regions/{region_id}/cleanup")
async def cleanup_region_text(
    region_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Use LLM to clean up OCR text for a region."""
    region = db.query(ExtractedText).join(Document).join(Exam).filter(
        ExtractedText.id == region_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    
    if not region.raw_text:
        raise HTTPException(status_code=400, detail="No raw text to clean up. Run OCR first.")
    
    started = time.perf_counter()
    fallback_used = False
    changed = False
    cleaned_text = region.raw_text
    model_used = llm_service.model
    tokens_used = None
    processing_time_ms = 0
    llm_error = None

    try:
        result = await llm_service.cleanup_ocr_text(region.raw_text)
        parsed = result.parsed_response if isinstance(result.parsed_response, dict) else {}
        parsed_text = str(parsed.get("corrected_text") or "").strip() if parsed else ""
        cleaned_text = parsed_text or (result.raw_response or "").strip() or region.raw_text
        changed = cleaned_text.strip() != (region.raw_text or "").strip()
        model_used = result.model_used or llm_service.model
        tokens_used = result.tokens_used
        processing_time_ms = result.processing_time_ms or 0

        # Save LLM response for audit trail
        llm_response = LLMResponse(
            exam_id=region.document.exam_id,
            request_type="text_cleanup",
            input_text=region.raw_text,
            prompt_used="cleanup_ocr_text",
            raw_response=result.raw_response,
            parsed_response=result.parsed_response,
            model_used=model_used,
            processing_time_ms=processing_time_ms,
            tokens_used=tokens_used
        )
        db.add(llm_response)
    except Exception as e:
        # Non-fatal fallback: keep original OCR text if cleanup fails/unavailable.
        fallback_used = True
        llm_error = str(e)

    region.processed_text = cleaned_text
    db.commit()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    print(
        "[Cleanup] "
        f"region_id={region.id} "
        f"doc_type={region.document.doc_type} "
        f"provider=ollama "
        f"model={model_used} "
        f"changed={changed} "
        f"fallback_used={fallback_used} "
        f"elapsed_ms={elapsed_ms}",
        flush=True
    )

    payload = {
        "region_id": region_id,
        "raw_text": region.raw_text,
        "processed_text": region.processed_text,
        "provider": "ollama",
        "model": model_used,
        "changed": changed,
        "fallback_used": fallback_used,
        "processing_time_ms": processing_time_ms if processing_time_ms else elapsed_ms,
        "tokens_used": tokens_used,
        "error": llm_error
    }
    return payload


@router.get("/health/ocr")
async def check_ocr_health():
    """Check if OCR service is ready."""
    try:
        # This will trigger lazy loading of the model
        return {"status": "ready", "model": ocr_service.model_name}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/health/llm")
async def check_llm_health():
    """Check if LLM service (Ollama) is available."""
    is_healthy = await llm_service.check_health()
    if is_healthy:
        return {"status": "ready", "model": llm_service.model}
    else:
        return {"status": "error", "message": "Ollama not available or model not loaded"}
