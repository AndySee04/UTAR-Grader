from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class MarkingGuideCreate(BaseModel):
    question_number: str = Field(..., max_length=50)
    question_text: Optional[str] = None
    question_type: Optional[str] = Field(None, pattern="^(mcq|structured|open_ended)$")
    answer_scheme: Optional[str] = None
    max_marks: Optional[float] = Field(None, ge=0)


class MarkingGuideUpdate(BaseModel):
    question_number: Optional[str] = Field(None, max_length=50)
    question_text: Optional[str] = None
    question_type: Optional[str] = Field(None, pattern="^(mcq|structured|open_ended)$")
    answer_scheme: Optional[str] = None
    max_marks: Optional[float] = Field(None, ge=0)


class MarkingGuideResponse(BaseModel):
    id: str
    exam_id: str
    question_number: str
    question_text: Optional[str]
    question_type: Optional[str]
    answer_scheme: Optional[str]
    max_marks: Optional[float]
    is_modified: bool
    created_at: datetime
    modified_at: Optional[datetime]

    class Config:
        from_attributes = True


class MarkingGuideListResponse(BaseModel):
    id: str
    question_number: str
    question_text: Optional[str]
    question_type: Optional[str]
    max_marks: Optional[float]
    is_modified: bool

    class Config:
        from_attributes = True


class GenerateGuideRequest(BaseModel):
    use_llm: bool = True  # If false, just structure from OCR text


class GenerateGuideResponse(BaseModel):
    exam_id: str
    questions_generated: int
    total_marks: float
    marking_guide: List[MarkingGuideResponse]
