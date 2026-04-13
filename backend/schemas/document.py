from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class DocumentUpload(BaseModel):
    doc_type: str = Field(..., pattern="^(question_paper|answer_scheme|student_answer)$")
    file_name: Optional[str] = Field(None, max_length=255)


class DocumentResponse(BaseModel):
    id: str
    exam_id: str
    doc_type: str
    file_path: str
    file_name: Optional[str]
    page_count: Optional[int]
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    id: str
    doc_type: str
    file_name: Optional[str]
    page_count: Optional[int]
    uploaded_at: datetime

    class Config:
        from_attributes = True


class PageImageResponse(BaseModel):
    page_number: int
    image_url: str
    width: int
    height: int


class CropRegion(BaseModel):
    page_number: int
    x: int
    y: int
    width: int
    height: int
    region_type: str = Field(..., pattern="^(question|answer_scheme|student_answer)$")
    question_number: Optional[str] = None


class CropRegionResponse(BaseModel):
    id: str
    document_id: str
    page_number: int
    bounding_box: dict
    region_type: str
    question_number: Optional[str]
    raw_text: Optional[str]
    processed_text: Optional[str]
    marks: Optional[float] = None

    class Config:
        from_attributes = True
