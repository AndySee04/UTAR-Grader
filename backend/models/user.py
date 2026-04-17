import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, LargeBinary
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    name = Column(String(255))
    profile_picture = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    exams = relationship("Exam", back_populates="user", cascade="all, delete-orphan")
