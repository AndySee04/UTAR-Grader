from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Tuple
import io
import uuid
import os
import sys
import zipfile
import shutil
from pathlib import Path
import secrets
from datetime import datetime, timedelta
from pydantic import BaseModel
from PIL import Image, ImageOps
try:
    import cv2
except Exception:
    cv2 = None
try:
    import numpy as np
except Exception:
    np = None

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
from config import UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS, FRONTEND_BASE_URL

router = APIRouter()

CAPTURE_SESSION_TTL_MINUTES = 90
_capture_sessions: Dict[str, dict] = {}


class CaptureSessionCreateRequest(BaseModel):
    doc_type: str
    frontend_base_url: Optional[str] = None


class CaptureSessionFinalizeRequest(BaseModel):
    token: str
    page_ids: Optional[List[str]] = None


class CaptureSessionContinueRequest(BaseModel):
    token: str


class CaptureSessionExitRequest(BaseModel):
    token: str


def _capture_session_dir(exam_id: str, session_id: str) -> Path:
    return UPLOAD_DIR / exam_id / "_capture_sessions" / session_id


def _cleanup_expired_capture_sessions() -> None:
    now = datetime.utcnow()
    expired = [
        sid for sid, s in _capture_sessions.items()
        if isinstance(s.get("expires_at"), datetime) and s["expires_at"] < now
    ]
    for sid in expired:
        session = _capture_sessions.get(sid) or {}
        exam_id = session.get("exam_id")
        if exam_id:
            session_dir = _capture_session_dir(exam_id, sid)
            if session_dir.exists():
                shutil.rmtree(session_dir, ignore_errors=True)
        _capture_sessions.pop(sid, None)


def _validate_capture_doc_type(doc_type: str) -> str:
    value = (doc_type or "").strip()
    if value not in {"question_paper", "student_answer"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Capture sessions only support question_paper and student_answer."
        )
    return value


def _create_capture_session_record(exam_id: str, doc_type: str, frontend_base_url: Optional[str] = None) -> dict:
    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(24)
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=CAPTURE_SESSION_TTL_MINUTES)
    base_url = (frontend_base_url or FRONTEND_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        base_url = FRONTEND_BASE_URL
    session = {
        "id": session_id,
        "token": token,
        "exam_id": exam_id,
        "doc_type": doc_type,
        "status": "pending",
        "document_id": None,
        "pages": [],
        "next_session_id": None,
        "parent_session_id": None,
        "exit_requested": False,
        "created_at": now,
        "expires_at": expires_at,
        "frontend_base_url": base_url,
    }
    _capture_sessions[session_id] = session
    return session


def _build_capture_mobile_url(session: dict) -> str:
    return f"{session['frontend_base_url']}/capture/{session['id']}?token={session['token']}"


def _session_public_payload(session: dict) -> dict:
    return {
        "session_id": session["id"],
        "exam_id": session["exam_id"],
        "doc_type": session["doc_type"],
        "status": session["status"],
        "document_id": session.get("document_id"),
        "exit_requested": bool(session.get("exit_requested")),
        "page_count": len(session.get("pages") or []),
        "created_at": session["created_at"],
        "expires_at": session["expires_at"],
    }


def _capture_page_payload(session: dict, page: dict) -> dict:
    return {
        "id": page["id"],
        "index": page["index"],
        "width": page["width"],
        "height": page["height"],
        "processed_success": bool(page.get("processed_success")),
        "processing_note": page.get("processing_note"),
        "created_at": page["created_at"],
        "preview_url": (
            f"/api/capture-sessions/{session['id']}/pages/{page['id']}/image"
            f"?token={session['token']}"
        ),
    }


def _normalize_capture_image(image: Image.Image) -> Image.Image:
    return ImageOps.exif_transpose(image).convert("RGB")


def _order_quad_points(points):
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = points.astype("float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype="float32")


def _biggest_document_quad(contours):
    """
    Reference-style biggest 4-corner contour selection.
    Mirrors user's OpenCV approach.
    """
    biggest = np.array([])
    max_area = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 1000:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.015 * peri, True)
            if area > max_area and len(approx) == 4:
                biggest = approx
                max_area = area
    return biggest


def _detect_document_quad_points(bgr_img):
    """
    Detect a 4-corner document contour on a downscaled working image,
    then map points back to the original-resolution image.
    """
    h, w = bgr_img.shape[:2]
    max_side = max(h, w)
    scale = 1.0
    work = bgr_img
    if max_side > 1280:
        scale = 1280.0 / float(max_side)
        work = cv2.resize(bgr_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 20, 30, 30)
    edges = cv2.Canny(gray, 10, 20)
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    top_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    biggest = _biggest_document_quad(top_contours)
    if biggest.size == 0:
        return None

    quad = biggest.reshape(4, 2).astype("float32")
    if scale != 1.0:
        quad = quad / scale
    return quad


def _deskew_bgr_image(bgr_img):
    """
    Detect dominant document angle and deskew using affine rotation.
    Uses edges + largest contour -> minAreaRect angle.
    """
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 60, 160)

    # Prefer Hough dominant line angle for deskew.
    angle_candidates = []
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=100,
        minLineLength=max(80, int(min(bgr_img.shape[:2]) * 0.15)),
        maxLineGap=20,
    )
    if lines is not None:
        for ln in lines[:200]:
            x1, y1, x2, y2 = ln[0]
            dx = x2 - x1
            dy = y2 - y1
            if abs(dx) < 5:
                continue
            angle = np.degrees(np.arctan2(dy, dx))
            # Keep mostly-horizontal lines; verticals are less stable for deskew.
            if -45.0 <= angle <= 45.0:
                angle_candidates.append(angle)

    if angle_candidates:
        angle = float(np.median(angle_candidates))
    else:
        # Fallback to minAreaRect angle from largest contour.
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return bgr_img
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < max(4000, int(bgr_img.shape[0] * bgr_img.shape[1] * 0.03)):
            return bgr_img
        rect = cv2.minAreaRect(largest)
        angle = rect[-1]
        if angle < -45:
            angle = 90 + angle

    h, w = bgr_img.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        bgr_img,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )


def _crop_foreground_bgr(bgr_img):
    """
    Create mask with Otsu threshold and crop to largest foreground contour.
    """
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Ensure document is white in mask; invert when needed.
    white_ratio = float(np.count_nonzero(mask)) / float(mask.size)
    if white_ratio < 0.25:
        mask = cv2.bitwise_not(mask)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return bgr_img

    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < max(4000, int(bgr_img.shape[0] * bgr_img.shape[1] * 0.03)):
        return bgr_img

    x, y, w, h = cv2.boundingRect(largest)
    pad = max(4, int(min(w, h) * 0.01))
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(bgr_img.shape[1], x + w + pad)
    y1 = min(bgr_img.shape[0], y + h + pad)
    cropped = bgr_img[y0:y1, x0:x1]
    if cropped.size == 0:
        return bgr_img
    return cropped


def _grayscale_for_ocr_bgr(bgr_img):
    """
    Convert processed page into enhanced grayscale for OCR.
    Returns 3-channel BGR image (gray tones).
    """
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.bilateralFilter(gray, 9, 50, 50)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def _warp_document_quad_bgr(bgr_img):
    """
    Detect 4-corner document contour, then perspective-warp using ORIGINAL image.
    This preserves sharpness while keeping contour detection stable.
    """
    detected_quad = _detect_document_quad_points(bgr_img)
    if detected_quad is None:
        return bgr_img, False

    rect = _order_quad_points(detected_quad)
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_width = int(max(width_a, width_b))
    # Use measured height to avoid stretching/blur from forced A4 ratio.
    max_height = int(max(height_a, height_b))
    if max_width < 80 or max_height < 80:
        return bgr_img, False

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1],
    ], dtype="float32")
    matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(bgr_img, matrix, (max_width, max_height))
    return warped, True


def _server_scan_capture_image(image: Image.Image) -> Tuple[Image.Image, bool, str]:
    """
    Server-side document detection/straighten+crop on laptop.
    Returns (image, success_flag, note).
    """
    normalized = _normalize_capture_image(image)
    if cv2 is None or np is None:
        return normalized, False, "opencv-unavailable"

    try:
        rgb = np.array(normalized)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        # Reference flow: contour-driven perspective first, then fine deskew + crop.
        warped, contour_found = _warp_document_quad_bgr(bgr)
        deskewed = _deskew_bgr_image(warped)
        cropped = _crop_foreground_bgr(deskewed)
        src_area = float(max(1, bgr.shape[0] * bgr.shape[1]))
        crop_area = float(max(1, cropped.shape[0] * cropped.shape[1]))
        # Require meaningful crop reduction; tiny edge trims should not be "success".
        crop_reduction = 1.0 - (crop_area / src_area)
        transformed = bool(crop_reduction >= 0.05 or warped.shape[:2] != bgr.shape[:2])
        # If largest contour is not found, force fallback (red border).
        processed_success = bool(contour_found and transformed)
        final_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        if not contour_found:
            note = "fallback-no-contour"
        else:
            note = "processed-cropped" if processed_success else "fallback-no-crop"
        return Image.fromarray(final_rgb).convert("RGB"), processed_success, note
    except Exception:
        return normalized, False, "processing-error"


def _save_document_bytes(
    *,
    exam_id: str,
    doc_type: str,
    content: bytes,
    source_filename: Optional[str],
    display_name: Optional[str]
) -> Document:
    ext = os.path.splitext(source_filename or "")[1].lower() or ".pdf"
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".pdf"
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / exam_id / filename
    (UPLOAD_DIR / exam_id).mkdir(parents=True, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)
    return _build_document_record(
        exam_id=exam_id,
        doc_type=doc_type,
        file_path=file_path,
        original_name=(display_name or source_filename or "")
    )


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


@router.post("/exams/{exam_id}/capture-sessions", status_code=status.HTTP_201_CREATED)
async def create_capture_session(
    exam_id: str,
    body: CaptureSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a QR/mobile capture session for one document upload."""
    _cleanup_expired_capture_sessions()
    doc_type = _validate_capture_doc_type(body.doc_type)

    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    session = _create_capture_session_record(exam_id, doc_type, body.frontend_base_url)
    mobile_url = _build_capture_mobile_url(session)
    return {
        **_session_public_payload(session),
        "mobile_url": mobile_url,
    }


@router.get("/exams/{exam_id}/capture-sessions/{session_id}")
async def get_capture_session_owner(
    exam_id: str,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get capture session status for desktop owner polling."""
    _cleanup_expired_capture_sessions()
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.user_id == current_user.id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    session = _capture_sessions.get(session_id)
    if not session or session.get("exam_id") != exam_id:
        raise HTTPException(status_code=404, detail="Capture session not found")
    return _session_public_payload(session)


@router.get("/capture-sessions/{session_id}")
async def get_capture_session_public(
    session_id: str,
    token: str = Query(...)
):
    """Get capture session status for phone client."""
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    return _session_public_payload(session)


@router.get("/capture-sessions/{session_id}/pages")
async def list_capture_session_pages(
    session_id: str,
    token: str = Query(...)
):
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    return {
        **_session_public_payload(session),
        "pages": [_capture_page_payload(session, p) for p in (session.get("pages") or [])],
    }


@router.post("/capture-sessions/{session_id}/pages", status_code=status.HTTP_201_CREATED)
async def upload_capture_session_page(
    session_id: str,
    token: str = Form(...),
    file: UploadFile = File(...)
):
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    if session.get("status") == "completed":
        raise HTTPException(status_code=409, detail="Session already completed")
    if session.get("status") == "cancelled":
        raise HTTPException(status_code=409, detail="Session was closed on desktop/phone.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Captured page must be an image file.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    try:
        pil_img = Image.open(io.BytesIO(content))
        normalized = _normalize_capture_image(pil_img)
        processed, processed_success, processing_note = _server_scan_capture_image(pil_img)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image upload.")

    pages = session.get("pages") or []
    page_id = str(uuid.uuid4())
    page_index = len(pages) + 1
    page_dir = _capture_session_dir(session["exam_id"], session_id)
    page_dir.mkdir(parents=True, exist_ok=True)
    source_path = page_dir / f"{page_index:03d}_{page_id}_source.png"
    processed_path = page_dir / f"{page_index:03d}_{page_id}_processed.png"
    preview_path = page_dir / f"{page_index:03d}_{page_id}_preview.jpg"
    normalized.save(source_path, format="PNG", optimize=True)
    processed.save(processed_path, format="PNG", optimize=True)
    processed.save(preview_path, format="JPEG", quality=78, optimize=True, progressive=True)

    page = {
        "id": page_id,
        "index": page_index,
        "source_path": str(source_path),
        "processed_path": str(processed_path),
        "preview_path": str(preview_path),
        "width": processed.width,
        "height": processed.height,
        "processed_success": bool(processed_success),
        "processing_note": processing_note,
        "created_at": datetime.utcnow(),
    }
    pages.append(page)
    session["pages"] = pages
    _capture_sessions[session_id] = session
    return _capture_page_payload(session, page)


@router.get("/capture-sessions/{session_id}/pages/{page_id}/image")
async def get_capture_session_page_image(
    session_id: str,
    page_id: str,
    token: str = Query(...)
):
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    page = next((p for p in (session.get("pages") or []) if p.get("id") == page_id), None)
    if not page:
        raise HTTPException(status_code=404, detail="Capture page not found")
    path = Path(page.get("preview_path") or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Capture page image missing")
    return FileResponse(str(path), media_type="image/jpeg")


@router.delete("/capture-sessions/{session_id}/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capture_session_page(
    session_id: str,
    page_id: str,
    token: str = Query(...)
):
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    if session.get("status") == "completed":
        raise HTTPException(status_code=409, detail="Session already completed")
    if session.get("status") == "cancelled":
        raise HTTPException(status_code=409, detail="Session was closed on desktop/phone.")

    pages = session.get("pages") or []
    remaining = []
    target = None
    for p in pages:
        if p.get("id") == page_id and target is None:
            target = p
        else:
            remaining.append(p)
    if target is None:
        raise HTTPException(status_code=404, detail="Capture page not found")

    target_source = Path(target.get("source_path") or "")
    target_processed = Path(target.get("processed_path") or "")
    target_preview = Path(target.get("preview_path") or "")
    if target_source.exists():
        target_source.unlink(missing_ok=True)
    if target_processed.exists():
        target_processed.unlink(missing_ok=True)
    if target_preview.exists():
        target_preview.unlink(missing_ok=True)

    for idx, p in enumerate(remaining, 1):
        p["index"] = idx
    session["pages"] = remaining
    _capture_sessions[session_id] = session
    return None


@router.post("/capture-sessions/{session_id}/finalize", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def finalize_capture_session(
    session_id: str,
    body: CaptureSessionFinalizeRequest,
    db: Session = Depends(get_db)
):
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if body.token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    if session.get("status") == "completed":
        existing_doc_id = session.get("document_id")
        if existing_doc_id:
            existing_doc = db.query(Document).filter(Document.id == existing_doc_id).first()
            if existing_doc:
                return existing_doc
        raise HTTPException(status_code=409, detail="Session already completed")

    pages = session.get("pages") or []
    if not pages:
        raise HTTPException(status_code=400, detail="No captured pages to finalize.")

    if body.page_ids:
        page_map = {p.get("id"): p for p in pages}
        ordered = []
        seen = set()
        for pid in body.page_ids:
            if pid in seen:
                continue
            page = page_map.get(pid)
            if not page:
                raise HTTPException(status_code=400, detail="Invalid page order payload.")
            ordered.append(page)
            seen.add(pid)
        if len(ordered) != len(pages):
            raise HTTPException(status_code=400, detail="All captured pages must be included.")
        pages = ordered
    else:
        pages = sorted(pages, key=lambda p: p.get("index", 0))

    pil_pages = []
    for p in pages:
        page_path = Path(p.get("processed_path") or p.get("source_path") or "")
        if not page_path.exists():
            raise HTTPException(status_code=400, detail="One or more capture pages are missing.")
        with Image.open(page_path) as img:
            pil_pages.append(img.convert("RGB"))

    pdf_buffer = io.BytesIO()
    first, rest = pil_pages[0], pil_pages[1:]
    first.save(pdf_buffer, format="PDF", save_all=True, append_images=rest)
    content = pdf_buffer.getvalue()
    if not content:
        raise HTTPException(status_code=500, detail="Failed to generate PDF from captured pages.")

    file_name = f"{session['doc_type']}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    document = _save_document_bytes(
        exam_id=session["exam_id"],
        doc_type=session["doc_type"],
        content=content,
        source_filename=file_name,
        display_name=file_name,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    session["status"] = "completed"
    session["document_id"] = document.id
    _capture_sessions[session_id] = session
    return document


@router.post("/capture-sessions/{session_id}/continue")
async def continue_capture_session(
    session_id: str,
    body: CaptureSessionContinueRequest
):
    """
    Create a follow-up student-answer capture session from phone after a successful upload.
    """
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if body.token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    if session.get("doc_type") != "student_answer":
        raise HTTPException(status_code=400, detail="Continue capture is only available for student answers.")
    if session.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Current capture session is not completed yet.")
    if session.get("exit_requested"):
        raise HTTPException(status_code=409, detail="Capture continuation was already closed.")

    existing_next_id = session.get("next_session_id")
    if existing_next_id:
        existing_next = _capture_sessions.get(existing_next_id)
        if existing_next and existing_next.get("status") != "completed":
            return {
                **_session_public_payload(existing_next),
                "mobile_url": _build_capture_mobile_url(existing_next),
            }

    next_session = _create_capture_session_record(
        exam_id=session["exam_id"],
        doc_type=session["doc_type"],
        frontend_base_url=session.get("frontend_base_url"),
    )
    next_session["parent_session_id"] = session["id"]
    _capture_sessions[next_session["id"]] = next_session
    session["next_session_id"] = next_session["id"]
    _capture_sessions[session_id] = session

    return {
        **_session_public_payload(next_session),
        "mobile_url": _build_capture_mobile_url(next_session),
    }


@router.post("/capture-sessions/{session_id}/exit")
async def exit_capture_session(
    session_id: str,
    body: CaptureSessionExitRequest
):
    """
    Explicitly stop chaining student-answer capture sessions from phone.
    If a next pending session already exists, cancel it so desktop QR closes.
    """
    _cleanup_expired_capture_sessions()
    session = _capture_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    if body.token != session.get("token"):
        raise HTTPException(status_code=403, detail="Invalid capture session token")
    if session.get("doc_type") != "student_answer":
        raise HTTPException(status_code=400, detail="Exit capture is only available for student answers.")
    if session.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Current capture session is not completed yet.")

    session["exit_requested"] = True
    _capture_sessions[session_id] = session

    next_session_id = session.get("next_session_id")
    if next_session_id:
        next_session = _capture_sessions.get(next_session_id)
        if next_session and next_session.get("status") == "pending":
            next_session["status"] = "cancelled"
            _capture_sessions[next_session_id] = next_session

    return _session_public_payload(session)


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
