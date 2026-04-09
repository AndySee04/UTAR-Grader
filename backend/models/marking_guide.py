import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Numeric, Boolean
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class MarkingGuide(Base):
    __tablename__ = "marking_guide"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(CHAR(36), ForeignKey("exams.id"), nullable=False)
    question_number = Column(String(50), nullable=False)
    question_text = Column(Text, nullable=True)
    question_type = Column(String(50), nullable=True)  # mcq, structured, open_ended
    answer_scheme = Column(Text, nullable=True)
    max_marks = Column(Numeric(5, 2), nullable=True)
    is_modified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, nullable=True)

    exam = relationship("Exam", back_populates="marking_guides")
    student_answers = relationship("StudentAnswer", back_populates="marking_guide", cascade="all, delete-orphan")
