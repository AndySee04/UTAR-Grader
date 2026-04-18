from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import asyncio
import hashlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.user import User
from schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    RegisterResponse,
    VerifyEmailResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from utils.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    decode_token,
    create_email_verification_token,
    create_password_reset_token,
    EMAIL_VERIFY_TYP,
    PASSWORD_RESET_TYP,
)
from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REGISTRATION_VERIFY_EXPIRE_HOURS,
    PASSWORD_RESET_EXPIRE_HOURS,
    smtp_configured,
)
from services.email_service import (
    registration_verify_url,
    send_registration_verification_email,
    password_reset_url,
    send_password_reset_email,
)

router = APIRouter()


def _picture_cache_version(user: User):
    if user.profile_picture:
        return hashlib.sha1(user.profile_picture).hexdigest()[:16]
    return None


def _user_to_response(user: User) -> UserResponse:
    picture_version = _picture_cache_version(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        profile_picture_url=(
            f"/api/account/profile-picture/{user.id}?v={picture_version}"
            if picture_version
            else None
        ),
        email_verified=bool(getattr(user, "email_verified", True)),
        created_at=user.created_at,
    )


def _send_verification_email_task(to_email: str, name, verify_jwt: str) -> None:
    verify_url = registration_verify_url(verify_jwt)
    send_registration_verification_email(
        to_email,
        name,
        verify_url,
        REGISTRATION_VERIFY_EXPIRE_HOURS,
    )


def _upsert_user_pending_verification(
    db: Session,
    existing: Optional[User],
    user_data: UserCreate,
    hashed_password: str,
) -> User:
    """Create or update unverified registration row; does not set email_verified=True."""
    if existing:
        existing.password = hashed_password
        existing.name = user_data.name
        db.commit()
        db.refresh(existing)
        return existing
    user_out = User(
        email=user_data.email,
        password=hashed_password,
        name=user_data.name,
        email_verified=False,
    )
    db.add(user_out)
    db.commit()
    db.refresh(user_out)
    return user_out


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create user with email_verified=False and send verification link (SMTP required)."""
    existing = db.query(User).filter(User.email == user_data.email).first()

    if existing and existing.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if not smtp_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification is not configured on this server. Set SMTP_USER and SMTP_PASSWORD.",
        )

    hashed_password = get_password_hash(user_data.password)
    user_out = _upsert_user_pending_verification(db, existing, user_data, hashed_password)

    verify_jwt = create_email_verification_token(user_out.id, user_out.email)
    await asyncio.to_thread(
        _send_verification_email_task,
        user_data.email,
        user_data.name,
        verify_jwt,
    )

    return RegisterResponse(
        message="Check your email to verify your address and complete registration.",
        email=user_data.email,
    )


@router.get("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    token: str = Query(..., min_length=20, max_length=8192),
    db: Session = Depends(get_db),
):
    """Mark email_verified from signed JWT (idempotent if already verified)."""
    payload = decode_token(token.strip())
    if not payload or payload.get("typ") != EMAIL_VERIFY_TYP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    user_id = payload.get("sub")
    claim_email = payload.get("email")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    if claim_email and user.email.lower() != str(claim_email).lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    if user.email_verified:
        return VerifyEmailResponse(
            message="Your email is verified. You can sign in.",
            email=user.email,
        )

    user.email_verified = True
    db.commit()

    return VerifyEmailResponse(
        message="Your email is verified. You can sign in.",
        email=user.email,
    )


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login with email and password, returns JWT token."""
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(user_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not getattr(user, "email_verified", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before signing in.",
        )

    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {"access_token": access_token, "token_type": "bearer"}


_FORGOT_PASSWORD_MSG = "If an account exists for that email, we sent password reset instructions."


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send password reset email (same generic response whether or not the email exists)."""
    if not smtp_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured on this server. Set SMTP_USER and SMTP_PASSWORD.",
        )
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not getattr(user, "email_verified", True):
        return MessageResponse(message=_FORGOT_PASSWORD_MSG)

    reset_jwt = create_password_reset_token(user.id, user.email)
    url = password_reset_url(reset_jwt)
    await asyncio.to_thread(
        send_password_reset_email,
        user.email,
        user.name,
        url,
        PASSWORD_RESET_EXPIRE_HOURS,
    )
    return MessageResponse(message=_FORGOT_PASSWORD_MSG)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Set a new password using the signed token from the reset email."""
    payload = decode_token(body.token.strip())
    if not payload or payload.get("typ") != PASSWORD_RESET_TYP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        )
    user_id = payload.get("sub")
    claim_email = payload.get("email")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        )
    if claim_email and user.email.lower() != str(claim_email).lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        )

    user.password = get_password_hash(body.new_password)
    db.commit()
    return MessageResponse(message="Your password has been updated. You can sign in.")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current logged-in user information."""
    picture_version = _picture_cache_version(current_user)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "profile_picture_url": (
            f"/api/account/profile-picture/{current_user.id}?v={picture_version}"
            if picture_version
            else None
        ),
        "email_verified": bool(getattr(current_user, "email_verified", True)),
        "created_at": current_user.created_at,
    }
