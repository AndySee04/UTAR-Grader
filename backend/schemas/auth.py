from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    profile_picture_url: Optional[str] = None
    email_verified: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)


class MessageResponse(BaseModel):
    message: str


class RegisterResponse(BaseModel):
    """Normal signup: only message + email until verified. Dev bypass may include user + token."""

    message: str
    email: EmailStr
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None


class VerifyEmailResponse(BaseModel):
    message: str
    email: EmailStr
