# UTAR Grader — Auto-Grading Website

UTAR Grader is an AI-assisted exam grading system using OCR (TrOCR) and LLMs (Ollama/OpenRouter) to assist teachers.

## Features

| **Feature** | **Description** |
|--------|------------|
| **Document Uploading** | Upload exam question papers (PDF) and student answer sheets (PDF/ZIP) via local upload or document scanning using a mobile device. |
| **Manual Cropping of Question Regions** | Draw regions for each question to perform line detection and text extraction (OpenCV + TrOCR), followed by text cleanup (Ollama). |
| **Manual Cropping of Student Answer Regions** | Draw regions for each student answer to perform line detection and text extraction (CRAFT via EasyOCR + TrOCR). |
| **Marking Guide Template Generation** | Generate a marking guide template based on the extracted questions for users to fill in the answer scheme. |
| **AI Grading** | Select an LLM grading provider (Ollama/OpenRouter) to grade student answers automatically. |
| **Generate Report** | Export grading reports in PDF and Excel formats. |
| **Email Notification** | Send account verification, password reset, and grading completion emails to users (Gmail SMTP). |

## System Architecture

| Layer | Technology |
|------|-----------|
| Frontend Layer | React + Vite + TailwindCSS |
| API Layer | REST API (FastAPI) behind Cloudflare |
| OCR Services | OpenCV / CRAFT (via EasyOCR) + TrOCR <br>(`microsoft/trocr-base-printed` for question papers, <br>`microsoft/trocr-large-handwritten` for student answers) |
| LLM Services | Llama 3.1 8B via Ollama / OpenRouter |
| Report Services | ReportLab (PDF) + OpenPyXL (Excel) |
| Email Services | Gmail SMTP |
| Database Layer | SQLite |
| GPU (Recommended) | NVIDIA RTX 4060 |

## Grading Workflow

- **Stage 1 - Upload Document**
   - Upload the **question paper** (PDF).
   - Upload one or more **student answer sheets** (PDF or ZIP).

- **Stage 2 - Crop Document Region**
   - **Crop Question Paper**
      - Open the question paper, draw regions over each question area.
      - After cropping, OCR is performed on each region to extract:
         - Question text
         - Marks allocation
      - Optional: Apply **auto-cleanup** (Ollama) after OCR to fix spelling errors and grammar mistakes.
   - **Crop Student Answer Sheet**
      - Open each student document, draw regions over each answer area
      - After cropping, OCR is performed on each region to extract:
         - Answer text

- **Stage 3 - Generate Marking Guide Template**
   - Click **Start Processing**:
      -  The system reads extracted question text (stored in `ExtractedText`)
      -  The system automatically generates a marking guide template: one entry per cropped region with:
         -  Question number
         -  Question text
         -  Marks allocation
   - In the **Marking Guide** stage:
      -  Fill in the **answer guide** (stored in `marking_guide.answer_scheme`) for each question.

- **Stage 4 - Grading**
   - **Select LLM Grading Provider**:
      - Choose the preferred LLM provider for grading student answers
         - **Ollama**
            - Marks scored
            - AI feedback
            - AI confidence score 
         - **OpenRouter** (No AI confidence score)
            - Marks scored
            - AI feedback
   - Click **Start Grading**:
      - The system will compare each student's answer against the marking guide using the selected LLM.
      - After grading, a grading completion email (attached with generated reports) is generated and sent to the user.
   -  **View Graded Results**:
      - Lecturers can review all graded student answer sheets.
      - Optional: Override scores manually if needed (overrides are saved immediately) and regenerate new Excel/PDF reports.

## Prerequisites

- Python 3.11+
- Node.js 18+
- NVIDIA GPU with CUDA (recommended for TrOCR acceleration)
- Ollama installed ([https://ollama.ai](https://ollama.ai))
- (Optional) OpenRouter API key configured ([https://openrouter.ai/](https://openrouter.ai/))

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
│   ├── database.py             # Database setup
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

The SQLite database is created in `backend/utar_grader.db` by default.

## Development Progress

See [TASKS.md](./TASKS.md) for detailed implementation progress.

## License

MIT License
