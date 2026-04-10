from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
from config import UPLOAD_DIR
from model_loader import load_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    init_db()
    UPLOAD_DIR.mkdir(exist_ok=True)
    print("Database initialized and upload directory ready.")
    load_models()
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="Auto-Grading API",
    description="API for automatic exam paper grading using OCR and LLM",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Auto-Grading API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Routes
from routes.auth import router as auth_router
from routes.exams import router as exams_router
from routes.documents import router as documents_router
from routes.processing import router as processing_router
from routes.marking_guide import router as marking_guide_router
from routes.grading import router as grading_router
from routes.reports import router as reports_router
from routes.account import router as account_router

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(exams_router, prefix="/api/exams", tags=["Exams"])
app.include_router(documents_router, prefix="/api", tags=["Documents"])
app.include_router(processing_router, prefix="/api", tags=["Processing"])
app.include_router(marking_guide_router, prefix="/api", tags=["Marking Guide"])
app.include_router(grading_router, prefix="/api", tags=["Grading"])
app.include_router(reports_router, prefix="/api", tags=["Reports"])
app.include_router(account_router, prefix="/api/account", tags=["Account"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
