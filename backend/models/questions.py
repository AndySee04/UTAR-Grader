import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(CHAR(36), ForeignKey("exams.id"), nullable=False)
    question_number = Column(String(50), nullable=False)
    question_text = Column(Text, nullable=True)
    extracted_text_id = Column(CHAR(36), ForeignKey("extracted_text.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    exam = relationship("Exam", back_populates="questions")
    student_answers = relationship("StudentAnswer", back_populates="question")
