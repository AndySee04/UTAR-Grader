# Auto-Grading Website

An automated exam paper grading system using OCR (CRAFT + TrOCR) and LLM (Ollama) for teachers.

## Features

- Upload exam question papers and student answer sheets (PDF)
- **Region-based question paper cropping**: draw regions per question; each region is OCR‑ed and stored with its question number and marks
- **Manual cropping of student answers**: draw regions per document, OCR runs on each cropped region; progress is saved so teachers can resume later
- **Start Processing** builds the marking guide directly from cropped **question paper regions** (no separate answer‑scheme PDF needed)
- Automatic text extraction using CRAFT + TrOCR for cropped student answers (line detection first, then line-level recognition)
- AI-powered marking guide generation from cropped question regions
- Automated grading with LLM using per‑question cropped student answers and your answer guides
- Teacher override for scores
- Export results to Excel and PDF

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite + TailwindCSS
- **Database**: SQLite (development) / PostgreSQL (production)
- **OCR**: CRAFT (EasyOCR detector) + TrOCR (microsoft/trocr-base-printed for question papers, microsoft/trocr-large-handwritten for student answers)
- **LLM**: Ollama + Llama 3 / Mistral
- **GPU**: NVIDIA RTX 4060 recommended

## Workflow

- **Step 1 – Upload & Crop**
   - Upload the **question paper** PDF and one or more **student answer** PDFs.
   - **Crop the question paper**: open the question paper, draw regions around each question; OCR runs per region and the extracted text (without trailing “x marks”) plus marks value are saved.
   - Optional **auto-cleanup** can run immediately after OCR for question regions (Ollama), with safe fallback to original OCR text if Ollama is unavailable.
   - **Crop each student answer**: open each student document, draw regions over answer areas; OCR runs per region and the per‑question answer text is saved.
   - For student answer regions, OCR uses **CRAFT text line detection** first, then applies **TrOCR per detected line**, then merges lines into final extracted text.
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

### Grading: optional “AI confidence” (logprobs)

When you run automated grading, the backend asks the chat API for **completion logprobs** (where supported). It stores a **lexical** confidence score per question on `grades.confidence`: the **geometric mean** of the model’s chosen token probabilities, i.e. **exp(mean(logprob))** over completion tokens, clamped to **[0, 1]**—not a guarantee the mark is “correct.”

- **Ollama**: use a version whose **Chat API** returns a top-level `logprobs` array ([Ollama Chat API](https://docs.ollama.com/api/chat)). If the server rejects the request, the backend retries once without logprobs; confidence is then omitted (`null`).
- **OpenRouter**: logprobs depend on the **upstream model**. Unsupported parameters trigger a retry without logprobs.

Older graded rows or failed logprob requests show **no** confidence in the UI/PDF until you re-run grading.

## OCR tuning (CRAFT + TrOCR)

Use `.env` to control CRAFT detection behavior:

- `CRAFT_PRESET=balanced|faint_handwriting|strict`
- `CRAFT_TEXT_THRESHOLD`
- `CRAFT_LINK_THRESHOLD`
- `CRAFT_LOW_TEXT`
- `OCR_DIAGNOSTICS=1` (optional debug logs)

Preset values are defaults, and numeric threshold env values override preset values.

### Recommended tuning checklist

1. Start with `CRAFT_PRESET=balanced`.
2. Run OCR on a sample with known head/tail misses.
3. If misses remain, switch to `faint_handwriting`.
4. If over-detection/noisy boxes appear, raise `CRAFT_TEXT_THRESHOLD` and/or `CRAFT_LINK_THRESHOLD`.
5. Re-run the same sample and compare line coverage and extracted text quality.

### Troubleshooting

- **Ollama cleanup fails**: cleanup endpoint now falls back to original OCR text (non-fatal), so processing continues.
- **CRAFT misses start/end characters**: try `CRAFT_PRESET=faint_handwriting`, then lower `CRAFT_TEXT_THRESHOLD` slightly.
- **CRAFT detects too much noise**: use `CRAFT_PRESET=strict` or increase thresholds.

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
