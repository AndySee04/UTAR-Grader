from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import uuid
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from models.exam import Exam
from models.document import Document
from models.extracted_text import ExtractedText
from schemas.document import DocumentResponse, DocumentListResponse, CropRegion, CropRegionResponse
from utils.auth import get_current_user
from config import UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS

router = APIRouter()


def validate_file(file: UploadFile):
    """Validate uploaded file type and size."""
    # Check extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return ext


@router.post("/exams/{exam_id}/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    exam_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    student_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a PDF document for an exam."""
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
    ext = validate_file(file)
    
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
    
    # Get page count (will be updated after processing)
    page_count = None
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(file_path))
        page_count = len(doc)
        doc.close()
    except:
        pass
    
    # Create document record
    document = Document(
        exam_id=exam_id,
        doc_type=doc_type,
        file_path=str(file_path),
        student_name=student_name,
        page_count=page_count
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
        ext = validate_file(file)
        
        # Extract student name from filename (remove extension)
        student_name = os.path.splitext(file.filename)[0]
        
        file_id = str(uuid.uuid4())
        filename = f"{file_id}{ext}"
        file_path = UPLOAD_DIR / exam_id / filename
        
        try:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                continue  # Skip oversized files
            
            with open(file_path, "wb") as f:
                f.write(content)
        except:
            continue
        
        # Get page count
        page_count = None
        try:
            import fitz
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            doc.close()
        except:
            pass
        
        document = Document(
            exam_id=exam_id,
            doc_type=doc_type,
            file_path=str(file_path),
            student_name=student_name,
            page_count=page_count
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
    
    # Delete file from disk
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
    except:
        pass
    
    db.delete(document)
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
