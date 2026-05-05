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

### Stage 1 - Upload Document
![Stage 1 - Upload Document](./Stage%201%20-%20Upload%20Document.png)

**(a)** Upload the **question paper** (PDF).

**(b)** Upload one or more **student answer sheets** (PDF or ZIP).

**(c)** Cick on **Process Documents** button.

_____________________________________________________________________________________________

### Stage 2 - Crop Document Region

![Stage 2 - Document Process](./Stage%202%20-%20Document%20Process.png)

**(a)** Crop question paper.

![Stage 2 - Document Process (Question)](./Stage%202%20-%20Document%20Process%20%28Question%29.png)
   
   - Open the question paper, draw regions over each question area.
   - After cropping, OCR is performed on each region to extract the question text and marks allocation.
   - Optional: Apply **auto-cleanup** (Ollama) after OCR to fix spelling errors and grammar mistakes.

**(b)** Crop student answer sheet.

![Stage 2 - Document Process (Student Answer)](./Stage%202%20-%20Document%20Process%20%28Student%20Answer%29.png)

   - Open each student document, draw regions over each answer area
   - After cropping, OCR is performed on each region to extract the answer text.

_____________________________________________________________________________________________

### Stage 3 - Generate Marking Guide Template

![Stage 3 - Generate Marking Guide Template](./Stage%203%20-%20Generate%20Marking%20Guide%20Template.png)

**(a)** Click on **Start Processing** button.
   -  The system reads extracted question text (stored in `ExtractedText`)
   -  The system automatically generates a marking guide template: one entry per cropped region with:
      -  Question number
      -  Question text
      -  Marks allocation

**(b)** Fill in the **answer guide** (stored in `marking_guide.answer_scheme`) for each question.

_____________________________________________________________________________________________

### Stage 4 - Grading

![Stage 4 - Grading (Ollama)](./Stage%204%20-%20Grading%20%28Ollama%29.png)
![Stage 4 - Grading (OpenRouter)](./Stage%204%20-%20Grading%20%28OpenRouter%29.png)

**(a)** Select the desired LLM grading provider.
   - **Ollama**
      - Marks scored
      - AI feedback
      - AI confidence score
   - **OpenRouter**
      - Marks scored
      - AI feedback

**(b)** Click on **Start Grading** button.
   - The system will compare each student's answer against the marking guide using the selected LLM.
   - After all grading tasks are done:
      - Exam status is updated as "Completed". <br>
        ![Stage 4 - Grading (Completed status)](./Stage%204%20-%20Grading%20%28Completed%20status%29.png)
      - Grading completion email (attached with generated reports) is generated and sent to the user. <br>
        ![Stage 4 - Grading (Grading completion email)](./Stage%204%20-%20Grading%20%28Grading%20completion%20email%29.png)

**(c)** View the graded result page.
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

ollama pull llama3.1:8b
```

Ollama is required for grading (and any other LLM features you enable).

## AI Confidence Score (Ollama only)
During automated grading, the backend requests completion log probabilities (logprobs) from the chat API and computes an AI confidence score for each graded answer based on token probabilities. 

- Stored in `grades.confidence`.
- Computed as the geometric mean of token probabilities, expressed as exp(mean(logprob)) across all completion tokens.
- Ranges from 0 to 1.

Note that this score represents the model’s confidence in its generated response, and does not guarantee that the assigned mark is correct.

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
