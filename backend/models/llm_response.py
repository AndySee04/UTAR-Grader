import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, JSON
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class LLMResponse(Base):
    __tablename__ = "llm_responses"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(CHAR(36), ForeignKey("exams.id"), nullable=False)
    request_type = Column(String(50), nullable=False)  # text_cleanup, guide_generation, grading
    input_text = Column(Text, nullable=True)
    prompt_used = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    parsed_response = Column(JSON, nullable=True)
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    exam = relationship("Exam", back_populates="llm_responses")
    grades = relationship("Grade", back_populates="llm_response")
