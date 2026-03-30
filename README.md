# Auto-Grading Website

An automated exam paper grading system using OCR (TrOCR) and LLM (Ollama) for teachers.

## Features

- Upload exam question papers and student answer sheets (PDF)
- **Region-based question paper cropping**: draw regions per question; each region is OCR‑ed and stored with its question number and marks
- **Manual cropping of student answers**: draw regions per document, OCR runs on each cropped region; progress is saved so teachers can resume later
- **Start Processing** builds the marking guide directly from cropped **question paper regions** (no separate answer‑scheme PDF needed)
- Automatic text extraction using TrOCR (printed text for question papers, handwriting for student answers)
- AI-powered marking guide generation from cropped question regions
- Automated grading with LLM using per‑question cropped student answers and your answer guides
- Teacher override for scores
- Export results to Excel and PDF

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite + TailwindCSS
- **Database**: SQLite (development) / PostgreSQL (production)
- **OCR**: TrOCR (microsoft/trocr-base-printed for question papers, microsoft/trocr-base-handwritten for student answers)
- **LLM**: Ollama + Llama 3 / Mistral
- **GPU**: NVIDIA RTX 4060 recommended

## Workflow

- **Step 1 – Upload & Crop**
   - Upload the **question paper** PDF and one or more **student answer** PDFs.
   - **Crop the question paper**: open the question paper, draw regions around each question; OCR runs per region and the extracted text (without trailing “x marks”) plus marks value are saved.
   - **Crop each student answer**: open each student document, draw regions over answer areas; OCR runs per region and the per‑question answer text is saved.
- **Step 2 – Review Marking Guide**  
   - Click **Start Processing**. The app reads the cropped **question paper regions** (and their extracted text stored in `ExtractedText`) and automatically builds a marking guide: one entry per cropped region, including question number, question text, and marks.
   - In the **Marking Guide** step, review and edit question numbers, wording, marks, and write an **answer guide** for each question (stored in `marking_guide.answer_scheme`).
- **Step 3 – Grade**  
   - Start grading to compare each student's cropped answer text with your answer guide using the LLM and assign a **whole‑number score** per question.
   - Override scores manually if needed (overrides are saved immediately) and export results to Excel/PDF.

## Prerequisites

- Python 3.11+
- Node.js 18+
- NVIDIA GPU with CUDA (for TrOCR acceleration)
- Ollama installed ([https://ollama.ai](https://ollama.ai))

## Quick start

### Backend (FastAPI)

```bash
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

pip install -r requirements.txt

cd backend
python main.py
```

Backend runs at `http://localhost:8000` (docs: `http://localhost:8000/docs`).

### Frontend (Vite)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

### Ollama (LLM server)

```bash
ollama serve

ollama pull llama3:8b
```

Ollama is required for grading (and any other LLM features you enable).

## Debugging (optional)

### Log Ollama request/response (backend terminal)

To print the **exact Ollama request payload** and **raw response** in the backend terminal:

```powershell
$env:OLLAMA_DEBUG="1"
$env:OLLAMA_DEBUG_MAX_CHARS="8000"  # optional
```

Restart the backend after setting these.

### Verify GPU/CUDA

```python
# Run in Python to verify CUDA is available
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")
```

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

## Development Progress

See [TASKS.md](./TASKS.md) for detailed implementation progress.

## License

MIT License
