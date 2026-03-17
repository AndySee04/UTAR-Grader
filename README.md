# Auto-Grading Website

An automated exam paper grading system using OCR (TrOCR) and LLM (Ollama) for teachers.

## Features

- Upload exam question papers, answer schemes, and student answer sheets (PDF)
- **Optional question paper cropping** before processing to reduce processing time
- **Manual cropping of student answers**: draw regions per document, OCR runs on each cropped region; progress is saved so teachers can resume later
- **Start Processing** runs in the background (separate process): processes question paper and answer scheme only; question paper is skipped if already cropped
- Automatic text extraction using TrOCR (handwriting recognition)
- AI-powered marking guide generation (from question paper and answer scheme)
- Automated grading with LLM
- Teacher override for scores
- Export results to Excel and PDF

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite + TailwindCSS
- **Database**: SQLite (development) / PostgreSQL (production)
- **OCR**: TrOCR (microsoft/trocr-base-handwritten)
- **LLM**: Ollama + Llama 3 / Mistral
- **GPU**: NVIDIA RTX 4060 recommended

## Workflow

1. **Step 1 – Upload & Crop**
   - Upload the **question paper** PDF and one or more **student answer** PDFs.
   - **Crop the question paper**: open the question paper, draw regions around each question; OCR runs per region and the extracted text is saved in the backend.
   - **Crop each student answer**: open each student document, draw regions over answer areas; OCR runs per region. Cropped regions and extracted text are saved when you close the document.
2. **Step 2 – Build & Review Marking Guide**  
   - Click **Start Processing**. The app reads the cropped **question paper regions** (and their extracted text stored in `ExtractedText`) and automatically builds a marking guide: one entry per cropped region, including question number, question text, and marks.
   - Review and edit the generated marking guide (question numbers, wording, marks, and answer guides) in the **Marking Guide** step.
3. **Step 3 – Grade**  
   - Grade student papers against the marking guide. The LLM compares each student's cropped answer text with your answer guide and assigns a score.
   - Override scores manually if needed and export results.

## Prerequisites

- Python 3.11+
- Node.js 18+
- NVIDIA GPU with CUDA (for TrOCR acceleration)
- Ollama installed ([https://ollama.ai](https://ollama.ai))

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "Auto Exam Grading Website"
```

### 2. Backend Setup

```bash
# Create virtual environment (use venv or .venv)
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install and Run Ollama

```bash
# Download Ollama from https://ollama.ai

# In one terminal, start the Ollama server (keep this running):
ollama serve

# In another terminal, pull a model:
ollama pull llama3:8b
# Or for faster inference:
ollama pull mistral:7b
```

### 4. Verify GPU/CUDA (Optional but Recommended)

```python
# Run in Python to verify CUDA is available
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")
```

### 5. Run the Backend

From the project root, run the API from the `backend` directory:

```bash
cd backend
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

When you click **Start Processing** in the app, the API spawns a worker process (`scripts/process_exam_worker.py`) to run OCR in the background. The worker’s progress messages (e.g. “Page 1/3 — loading image…”) appear in the **same terminal** where you started the backend (`python main.py`). You can also run processing manually for an exam:

```bash
cd backend
python -m scripts.process_exam_worker <exam_id>
```

### 6. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Project Structure

```
Auto Exam Grading Website/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration
│   ├── database.py            # Database setup
│   ├── models/                 # SQLAlchemy models
│   ├── routes/                 # API endpoints
│   ├── services/               # Business logic (OCR, LLM, etc.)
│   ├── schemas/                # Pydantic schemas
│   ├── scripts/
│   │   └── process_exam_worker.py   # Background processing (question paper + answer scheme)
│   └── utils/                  # Utilities
├── frontend/
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   └── services/           # API client
│   └── public/
├── uploads/                    # Uploaded files storage
├── requirements.txt            # Python dependencies
├── TASKS.md                    # Implementation tracker
└── README.md
```

The SQLite database is created in `backend/auto_grade.db` by default.

## API Documentation

Once the backend is running, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables (Optional)

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./backend/auto_grade.db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b
```

## Development Progress

See [TASKS.md](./TASKS.md) for detailed implementation progress.

## License

MIT License
