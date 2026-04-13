import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Text, Numeric, Boolean
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class Grade(Base):
    __tablename__ = "grades"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_answer_id = Column(CHAR(36), ForeignKey("student_answers.id"), nullable=False)
    llm_response_id = Column(CHAR(36), ForeignKey("llm_responses.id"), nullable=True)
    score = Column(Numeric(5, 2), nullable=True)
    max_marks = Column(Numeric(5, 2), nullable=True)
    confidence = Column(Numeric(5, 2), nullable=True)
    feedback = Column(Text, nullable=True)
    is_overridden = Column(Boolean, default=False)
    original_score = Column(Numeric(5, 2), nullable=True)
    graded_at = Column(DateTime, default=datetime.utcnow)
    overridden_at = Column(DateTime, nullable=True)

    student_answer = relationship("StudentAnswer", back_populates="grade")
    llm_response = relationship("LLMResponse", back_populates="grades")
