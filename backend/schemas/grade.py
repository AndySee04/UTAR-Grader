from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class GradeResponse(BaseModel):
    id: str
    student_answer_id: str
    score: Optional[float]
    max_marks: Optional[float]
    confidence: Optional[float] = None
    feedback: Optional[str]
    is_overridden: bool
    original_score: Optional[float]
    graded_at: datetime

    class Config:
        from_attributes = True


class GradeUpdate(BaseModel):
    score: int = Field(..., ge=0)
    feedback: Optional[str] = None


class StudentGradeDetail(BaseModel):
    id: str
    question_number: str
    question_text: Optional[str]
    answer_scheme: Optional[str]
    student_answer: Optional[str]
    score: Optional[float]
    max_marks: Optional[float]
    confidence: Optional[float] = None
    feedback: Optional[str]
    is_overridden: bool


class StudentGradeSummary(BaseModel):
    document_id: str
    student_name: Optional[str]
    total_score: float
    total_max_marks: float
    percentage: float
    grades: List[StudentGradeDetail]


class ExamGradingSummary(BaseModel):
    exam_id: str
    exam_name: str
    status: str
    total_students: int
    graded_students: int
    average_percentage: Optional[float]
    students: List[StudentGradeSummary]


class StartGradingRequest(BaseModel):
    process_all: bool = True  # If false, only grade ungraded
    provider: str = "ollama"
    # Ignored when provider is ollama (server uses OLLAMA_MODEL from env only).
    model: Optional[str] = None


class StartGradingResponse(BaseModel):
    exam_id: str
    status: str
    message: str
    students_to_grade: int
    provider: str = "ollama"
    model: Optional[str] = None
