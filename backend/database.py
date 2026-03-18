from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import user, exam, document, extracted_text, marking_guide, llm_response, student_answer, grade
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)
    if "sqlite" in DATABASE_URL:
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE extracted_text ADD COLUMN display_order INTEGER"))
                conn.commit()
        except Exception:
            pass
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE grades ADD COLUMN confidence REAL"))
                conn.commit()
        except Exception:
            pass
