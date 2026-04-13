import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(CHAR(36), ForeignKey("exams.id"), nullable=False)
    doc_type = Column(String(50), nullable=False)  # question_paper, answer_scheme, student_answer
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=True)
    page_count = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    exam = relationship("Exam", back_populates="documents")
    extracted_texts = relationship("ExtractedText", back_populates="document", cascade="all, delete-orphan")
    student_answers = relationship("StudentAnswer", back_populates="document", cascade="all, delete-orphan")
    grading_summary = relationship("GradingSummary", back_populates="document", uselist=False, cascade="all, delete-orphan")
