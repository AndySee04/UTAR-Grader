from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
import sys
import os
import uuid
from pathlib import Path
from fastapi.responses import FileResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from schemas.auth import UserResponse, UserUpdate, PasswordChange, MessageResponse
from utils.auth import get_current_user, get_password_hash, verify_password
from config import UPLOAD_DIR

router = APIRouter()


def _user_response_payload(user: User):
    profile_picture_url = (
        f"/api/account/profile-picture/{user.id}"
        if user.profile_picture_path
        else None
    )
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_picture_url": profile_picture_url,
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
    """Upload or replace profile picture."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG, and WEBP are allowed.")

    profile_dir = UPLOAD_DIR / "profile_pictures"
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Remove previous picture if present
    if current_user.profile_picture_path:
        old_path = Path(current_user.profile_picture_path)
        if old_path.exists():
            try:
                old_path.unlink()
            except Exception:
                pass

    target = profile_dir / f"{current_user.id}-{uuid.uuid4().hex}{ext}"
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Profile picture must be 5MB or smaller.")

    with open(target, "wb") as f:
        f.write(content)

    current_user.profile_picture_path = str(target)
    db.commit()
    db.refresh(current_user)
    return _user_response_payload(current_user)


@router.delete("/profile-picture", response_model=UserResponse)
async def remove_profile_picture(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove current profile picture."""
    if current_user.profile_picture_path:
        old_path = Path(current_user.profile_picture_path)
        if old_path.exists():
            try:
                old_path.unlink()
            except Exception:
                pass
    current_user.profile_picture_path = None
    db.commit()
    db.refresh(current_user)
    return _user_response_payload(current_user)


@router.get("/profile-picture/{user_id}")
async def get_profile_picture(
    user_id: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.profile_picture_path:
        raise HTTPException(status_code=404, detail="Profile picture not found.")

    path = Path(user.profile_picture_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile picture not found.")

    return FileResponse(path)


@router.put("/password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change account password."""
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_data.new_password)
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
