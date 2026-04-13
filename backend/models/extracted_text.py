import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Float, JSON
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class ExtractedText(Base):
    __tablename__ = "extracted_text"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(CHAR(36), ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=True)
    region_type = Column(String(50), nullable=True)  # question, answer_scheme, student_answer
    question_number = Column(String(50), nullable=True)
    bounding_box = Column(JSON, nullable=True)  # {x, y, width, height}
    display_order = Column(Integer, nullable=True)  # user-defined order (Q1, Q2, ...)
    raw_text = Column(Text, nullable=True)
    processed_text = Column(Text, nullable=True)
    marks = Column(Float, nullable=True)
    extracted_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="extracted_texts")
    student_answer = relationship("StudentAnswer", back_populates="extracted_text", uselist=False)
