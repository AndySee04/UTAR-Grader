from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pathlib import Path
from fastapi.responses import Response
import hashlib
from PIL import Image
import io

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from schemas.auth import UserResponse, UserUpdate, PasswordChange, MessageResponse
from utils.auth import get_current_user, get_password_hash, verify_password

router = APIRouter()

_ALLOWED_PROFILE_PICTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _picture_cache_version(user: User):
    if user.profile_picture:
        return hashlib.sha1(user.profile_picture).hexdigest()[:16]
    return None


def _normalize_profile_picture_bytes(content: bytes) -> bytes:
    """
    Normalize uploaded avatar to JPEG bytes so schema only needs one blob column.
    """
    with Image.open(io.BytesIO(content)) as img:
        rgb = img.convert("RGB")
        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=88, optimize=True, progressive=True)
        return out.getvalue()


def _user_response_payload(user: User):
    picture_version = _picture_cache_version(user)
    profile_picture_url = (
        f"/api/account/profile-picture/{user.id}?v={picture_version}"
        if picture_version
        else None
    )
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_picture_url": profile_picture_url,
        "email_verified": bool(getattr(user, "email_verified", True)),
        "created_at": user.created_at,
    }


@router.get("", response_model=UserResponse)
async def get_account(
    current_user: User = Depends(get_current_user)
):
    """Get current user's account information."""
    return _user_response_payload(current_user)


@router.put("", response_model=UserResponse)
async def update_account(
    update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update account information."""
    if update.name is not None:
        current_user.name = update.name

    db.commit()
    db.refresh(current_user)

    return _user_response_payload(current_user)


@router.post("/profile-picture", response_model=UserResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload or replace profile picture (stored in database)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_PROFILE_PICTURE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG, WEBP, and GIF are allowed.")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Profile picture must be 5MB or smaller.")

    current_user.profile_picture = _normalize_profile_picture_bytes(content)

    db.commit()
    db.refresh(current_user)
    return _user_response_payload(current_user)


@router.delete("/profile-picture", response_model=UserResponse)
async def remove_profile_picture(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove current profile picture."""
    current_user.profile_picture = None
    db.commit()
    db.refresh(current_user)
    return _user_response_payload(current_user)


@router.get("/profile-picture/{user_id}")
async def get_profile_picture(
    user_id: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Profile picture not found.")

    if not user.profile_picture:
        raise HTTPException(status_code=404, detail="Profile picture not found.")

    return Response(
        content=user.profile_picture,
        media_type="image/jpeg",
    )


@router.put("/password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change account password."""
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    current_user.password = get_password_hash(password_data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


@router.delete("", response_model=MessageResponse)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete account and all associated data."""
    db.delete(current_user)
    db.commit()

    return {"message": "Account deleted successfully"}
