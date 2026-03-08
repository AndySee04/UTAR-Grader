import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(CHAR(36), ForeignKey("documents.id"), nullable=False)
    marking_guide_id = Column(CHAR(36), ForeignKey("marking_guide.id"), nullable=False)
    extracted_text_id = Column(CHAR(36), ForeignKey("extracted_text.id"), nullable=True)
    answer_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="student_answers")
    marking_guide = relationship("MarkingGuide", back_populates="student_answers")
    extracted_text = relationship("ExtractedText", back_populates="student_answer")
    grade = relationship("Grade", back_populates="student_answer", uselist=False, cascade="all, delete-orphan")
