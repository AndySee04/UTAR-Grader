from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from schemas.auth import UserResponse, UserUpdate, PasswordChange, MessageResponse
from utils.auth import get_current_user, get_password_hash, verify_password

router = APIRouter()


@router.get("", response_model=UserResponse)
async def get_account(
    current_user: User = Depends(get_current_user)
):
    """Get current user's account information."""
    return current_user


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
    
    return current_user


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
