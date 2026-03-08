import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class Exam(Base):
    __tablename__ = "exams"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="draft")  # draft, processing, grading, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="exams")
    documents = relationship("Document", back_populates="exam", cascade="all, delete-orphan")
    marking_guides = relationship("MarkingGuide", back_populates="exam", cascade="all, delete-orphan")
    llm_responses = relationship("LLMResponse", back_populates="exam", cascade="all, delete-orphan")
    grading_summaries = relationship("GradingSummary", back_populates="exam", cascade="all, delete-orphan")
