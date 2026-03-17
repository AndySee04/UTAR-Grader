"""
Standalone worker to process an exam (question paper + answer scheme).
Run: python -m scripts.process_exam_worker <exam_id> from the backend directory.
"""
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from database import SessionLocal
from routes.processing import process_exam_background


def main():
    exam_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not exam_id:
        print("Usage: python -m scripts.process_exam_worker <exam_id>", file=sys.stderr)
        sys.exit(1)
    db = SessionLocal()
    try:
        process_exam_background(exam_id, db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
