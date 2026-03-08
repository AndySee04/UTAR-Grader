# Auto-Grading Website

An automated exam paper grading system using OCR (TrOCR) and LLM (Ollama) for teachers.

## Features

- Upload exam question papers, answer schemes, and student answer sheets (PDF)
- Automatic text extraction using TrOCR (handwriting recognition)
- AI-powered marking guide generation
- Automated grading with LLM
- Teacher override for scores
- Export results to Excel and PDF

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + TailwindCSS
- **Database**: SQLite (development) / PostgreSQL (production)
- **OCR**: TrOCR (microsoft/trocr-base-handwritten)
- **LLM**: Ollama + Llama 3 / Mistral
- **GPU**: NVIDIA RTX 4060 recommended

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
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install Ollama and Download Model

```bash
# Download Ollama from https://ollama.ai
# Then pull a model:
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

```bash
cd backend
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 6. Frontend Setup (Coming Soon)

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
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── database.py          # Database setup
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # API endpoints
│   ├── services/            # Business logic (OCR, LLM, etc.)
│   ├── schemas/             # Pydantic schemas
│   └── utils/               # Utilities
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   └── services/        # API client
│   └── public/
├── uploads/                 # Uploaded files storage
├── db/                      # SQLite database (auto-created)
├── requirements.txt         # Python dependencies
├── TASKS.md                 # Implementation tracker
└── README.md
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables (Optional)

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./db/auto_grade.db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b
```

## Development Progress

See [TASKS.md](./TASKS.md) for detailed implementation progress.

## License

MIT License
