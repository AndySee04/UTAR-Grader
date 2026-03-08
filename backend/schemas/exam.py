from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class ExamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ExamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern="^(draft|processing|grading|completed)$")


class ExamResponse(BaseModel):
    id: str
    user_id: str
    name: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ExamListResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    document_count: int = 0
    student_count: int = 0

    class Config:
        from_attributes = True


class ExamDetailResponse(ExamResponse):
    document_count: int = 0
    student_count: int = 0
    graded_count: int = 0
    average_percentage: Optional[float] = None

    class Config:
        from_attributes = True
