from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import io
import uuid
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.extracted_text import ExtractedText
from models.student_answer import StudentAnswer
from models.grade import Grade
from models.llm_response import LLMResponse
from schemas.document import DocumentResponse, DocumentListResponse, CropRegion, CropRegionResponse
from utils.auth import get_current_user
from config import UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS

router = APIRouter()


def _allowed_extensions_for_doc_type(doc_type: str) -> set:
    if doc_type == "student_answer":
        return set(ALLOWED_EXTENSIONS).union({".zip"})
    return set(ALLOWED_EXTENSIONS)


def validate_file(file: UploadFile, doc_type: str):
    """Validate uploaded file type by document type."""
    ext = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = _allowed_extensions_for_doc_type(doc_type)
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(sorted(allowed_extensions))}"
        )
    return ext


def _safe_zip_member_path(base_dir: Path, member_name: str) -> Optional[Path]:
    member_path = Path(member_name)
    if member_path.is_absolute():
        return None
    resolved = (base_dir / member_path).resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return resolved


def _build_document_record(exam_id: str, doc_type: str, file_path: Path, original_name: Optional[str] = None) -> Document:
    page_count = None
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(file_path))
        page_count = len(doc)
        doc.close()
    except:
        pass

    return Document(
        exam_id=exam_id,
        doc_type=doc_type,
        file_path=str(file_path),
        file_name=(original_name or "").strip() or None,
        page_count=page_count
    )


@router.post("/exams/{exam_id}/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    exam_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    file_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a document for an exam."""
    # Validate doc_type
    if doc_type not in ["question_paper", "answer_scheme", "student_answer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document type. Must be: question_paper, answer_scheme, or student_answer"
        )
    
    # Check exam exists and belongs to user
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    # Validate file
    ext = validate_file(file, doc_type)
    if doc_type == "student_answer" and ext == ".zip":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZIP upload is only supported in the multiple-upload endpoint for student answers."
        )
    
    # Create unique filename
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / exam_id / filename
    
    # Create exam directory if not exists
    (UPLOAD_DIR / exam_id).mkdir(parents=True, exist_ok=True)
    
    # Save file
    try:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        with open(file_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Create document record
    document = _build_document_record(
        exam_id=exam_id,
        doc_type=doc_type,
        file_path=file_path,
        original_name=(file_name or file.filename or "")
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return document


@router.post("/exams/{exam_id}/upload-multiple", response_model=List[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def upload_multiple_documents(
    exam_id: str,
    files: List[UploadFile] = File(...),
    doc_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload multiple PDF documents (typically student answer sheets)."""
    # Validate doc_type
    if doc_type not in ["question_paper", "answer_scheme", "student_answer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document type"
        )
    
    # Check exam exists and belongs to user
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    # Create exam directory
    (UPLOAD_DIR / exam_id).mkdir(parents=True, exist_ok=True)
    
    documents = []
    for file in files:
        ext = validate_file(file, doc_type)
        
        # Preserve the original uploaded filename for display/tracking
        file_name = (file.filename or "").strip() or None

        try:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                continue  # Skip oversized files

            if doc_type == "student_answer" and ext == ".zip":
                extracted_any = False
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue

                        safe_member_path = _safe_zip_member_path(UPLOAD_DIR / exam_id, info.filename)
                        if safe_member_path is None:
                            continue

                        member_ext = safe_member_path.suffix.lower()
                        if member_ext != ".pdf":
                            continue

                        with zf.open(info) as member_file:
                            pdf_bytes = member_file.read()

                        if len(pdf_bytes) > MAX_FILE_SIZE:
                            continue

                        extracted_any = True
                        file_id = str(uuid.uuid4())
                        extracted_path = (UPLOAD_DIR / exam_id / f"{file_id}.pdf")
                        with open(extracted_path, "wb") as out_f:
                            out_f.write(pdf_bytes)

                        document = _build_document_record(
                            exam_id=exam_id,
                            doc_type=doc_type,
                            file_path=extracted_path,
                            original_name=os.path.basename(info.filename) or file_name
                        )
                        db.add(document)
                        documents.append(document)

                if not extracted_any:
                    continue
                continue

            file_id = str(uuid.uuid4())
            filename = f"{file_id}{ext}"
            file_path = UPLOAD_DIR / exam_id / filename
            with open(file_path, "wb") as f:
                f.write(content)
        except:
            continue

        document = _build_document_record(
            exam_id=exam_id,
            doc_type=doc_type,
            file_path=file_path,
            original_name=file_name
        )
        
        db.add(document)
        documents.append(document)
    
    db.commit()
    for doc in documents:
        db.refresh(doc)
    
    return documents


@router.get("/exams/{exam_id}/documents", response_model=List[DocumentListResponse])
async def list_documents(
    exam_id: str,
    doc_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all documents for an exam."""
    # Check exam exists and belongs to user
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    query = db.query(Document).filter(Document.exam_id == exam_id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    
    documents = query.order_by(Document.uploaded_at.desc()).all()
    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document details."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Capture linked LLM responses so we can remove newly-orphaned audit rows.
    llm_response_ids = [
        row[0]
        for row in (
            db.query(Grade.llm_response_id)
            .join(StudentAnswer, Grade.student_answer_id == StudentAnswer.id)
            .filter(
                StudentAnswer.document_id == document.id,
                Grade.llm_response_id.isnot(None)
            )
            .all()
        )
        if row and row[0]
    ]

    # Delete file from disk
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
    except:
        pass
    
    db.delete(document)
    db.flush()

    # Remove LLM responses no longer referenced by any grade.
    orphan_llm_ids = [
        lrid for lrid in llm_response_ids
        if db.query(Grade).filter(Grade.llm_response_id == lrid).first() is None
    ]
    if orphan_llm_ids:
        db.query(LLMResponse).filter(LLMResponse.id.in_(orphan_llm_ids)).delete(synchronize_session=False)

    db.commit()
    return None


@router.post("/{document_id}/crop", response_model=CropRegionResponse, status_code=status.HTTP_201_CREATED)
async def save_crop_region(
    document_id: str,
    crop_data: CropRegion,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a manually cropped region for OCR processing."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    next_order = db.query(func.coalesce(func.max(ExtractedText.display_order), -1)).filter(
        ExtractedText.document_id == document_id
    ).scalar() + 1

    extracted_text = ExtractedText(
        document_id=document_id,
        page_number=crop_data.page_number,
        region_type=crop_data.region_type,
        question_number=crop_data.question_number,
        display_order=next_order,
        bounding_box={
            "x": crop_data.x,
            "y": crop_data.y,
            "width": crop_data.width,
            "height": crop_data.height
        }
    )
    
    db.add(extracted_text)
    db.commit()
    db.refresh(extracted_text)
    
    return CropRegionResponse(
        id=extracted_text.id,
        document_id=extracted_text.document_id,
        page_number=extracted_text.page_number,
        bounding_box=extracted_text.bounding_box,
        region_type=extracted_text.region_type,
        question_number=extracted_text.question_number,
        raw_text=extracted_text.raw_text,
        processed_text=extracted_text.processed_text,
        marks=extracted_text.marks,
    )


@router.get("/{document_id}/regions", response_model=List[CropRegionResponse])
async def get_crop_regions(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all cropped regions for a document."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # SQLite doesn't support NULLS LAST; use coalesce so nulls sort last
    regions = db.query(ExtractedText).filter(
        ExtractedText.document_id == document_id
    ).order_by(
        func.coalesce(ExtractedText.display_order, 999999),
        ExtractedText.page_number,
        ExtractedText.id
    ).all()
    
    return [
        CropRegionResponse(
            id=r.id,
            document_id=r.document_id,
            page_number=r.page_number,
            bounding_box=r.bounding_box or {},
            region_type=r.region_type,
            question_number=r.question_number,
            raw_text=r.raw_text,
            processed_text=r.processed_text,
            marks=r.marks,
        )
        for r in regions
    ]


@router.put("/{document_id}/regions/order", status_code=status.HTTP_204_NO_CONTENT)
async def update_regions_order(
    document_id: str,
    body: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save the display order of regions (e.g. after drag reorder). Body: { \"region_ids\": [\"id1\", \"id2\", ...] }."""
    document = db.query(Document).join(Exam).filter(
        Document.id == document_id,
        Exam.user_id == current_user.id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    region_ids = body.get("region_ids") or []
    for idx, rid in enumerate(region_ids):
        r = db.query(ExtractedText).filter(
            ExtractedText.id == rid,
            ExtractedText.document_id == document_id
        ).first()
        if r:
            r.display_order = idx
    db.commit()
    return None
