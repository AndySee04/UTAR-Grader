# Auto-Grading Website - Implementation Tracker

## Project Overview

A web application for teachers to automatically grade exam papers using OCR (CRAFT + TrOCR) and LLM (Ollama).

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + TailwindCSS
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **OCR**: CRAFT (EasyOCR detector) + TrOCR
- **LLM**: Ollama + Llama 3 / Mistral
- **PDF Processing**: PyMuPDF
- **Auth**: JWT + bcrypt

---

## Phase 1: Project Setup

- [x] Create project folder structure
- [x] Initialize Git repository
- [x] Create Python virtual environment
- [x] Install backend dependencies
- [x] Set up database schema
- [x] Verify GPU/CUDA working with TrOCR
- [x] Install and configure Ollama

### Backend Files Created:

- [x] `backend/config.py` - Configuration settings
- [x] `backend/database.py` - Database connection and session
- [x] `backend/main.py` - FastAPI application entry point
- [x] `backend/models/*` - All database models
- [x] `backend/schemas/*` - All Pydantic schemas
- [x] `backend/routes/*` - All API routes
- [x] `backend/services/*` - PDF, OCR, CV, LLM, Report services
- [x] `backend/utils/auth.py` - JWT and password utilities

---

## Phase 2: Authentication

- [x] Implement password hashing utility (bcrypt)
- [x] Implement JWT token creation/validation
- [x] Create `/api/auth/register` endpoint
- [x] Create `/api/auth/login` endpoint
- [x] Create `/api/auth/me` endpoint
- [x] Create JWT middleware for protected routes
- [x] Frontend: Login page
- [x] Frontend: Registration page
- [x] Frontend: Auth context/state management

### Files Created:

- [x] `backend/utils/auth.py` - Password hashing, JWT utilities
- [x] `backend/routes/auth.py` - Auth endpoints
- [x] `backend/schemas/auth.py` - Pydantic schemas for auth
- [x] `frontend/src/pages/Login.jsx`
- [x] `frontend/src/pages/Register.jsx`
- [x] `frontend/src/services/api.js`
- [x] `frontend/src/context/AuthContext.jsx`

---

## Phase 3: Dashboard Layout

- [x] Create main dashboard with 3 tabs
- [x] Navigation component (header)
- [x] Tab routing (Grade Paper, Exam List, Account)
- [x] Protected route wrapper

### Files Created:

- [x] `frontend/src/pages/Dashboard.jsx`
- [x] `frontend/src/components/Navbar.jsx`
- [x] `frontend/src/components/ProtectedRoute.jsx` (in App.jsx)

---

## Phase 4: Grade Paper - Step 1 (Upload)

- [x] Create exam endpoint
- [x] PDF upload endpoint (single and multiple files)
- [x] File validation (type, size)
- [x] Store file metadata in database
- [x] Frontend: Upload wizard step 1
- [x] Frontend: Drag-drop file upload component
- [x] Frontend: Upload progress indicator

### Files Created:

- [x] `backend/routes/exams.py` - Exam CRUD endpoints
- [x] `backend/routes/documents.py` - Document upload endpoints
- [x] `backend/schemas/exam.py` - Exam schemas
- [x] `backend/schemas/document.py` - Document schemas
- [x] `frontend/src/pages/GradePaper.jsx` (includes upload, step wizard, file upload)

---

## Phase 5: Grade Paper - Step 2 (Process Documents)

- [x] PDF to images service (PyMuPDF) for converting uploaded PDFs into pages
- [x] OpenCV preprocessing (grayscale, threshold, denoise)
- [x] Text region detection (contours) and manual region drawing
- [x] TrOCR integration for **per‑region** text extraction
- [x] CRAFT-based **text line detection** for cropped student answers, then TrOCR **line-by-line**
- [x] Store extracted text and marks per region in `extracted_text` table
- [x] Frontend: Processing step with crop status and progress per student
- [x] Frontend: Question paper and student answer crop tools (current UI)

### Files Created:

- [x] `backend/services/pdf_service.py` - PDF processing
- [x] `backend/services/ocr_service.py` - TrOCR wrapper
- [x] `backend/services/cv_service.py` - OpenCV detection
- [x] `backend/services/llm_service.py` - Ollama wrapper
- [x] `backend/routes/processing.py` - Processing endpoints
- [x] `frontend/src/components/ImageCropper.jsx`
- [x] `frontend/src/components/RegionList.jsx`

---

## Phase 6: Grade Paper - Step 3 (Marking Guide)

- [x] Build marking guide directly from cropped **question paper regions** (no separate answer‑scheme PDF)
- [x] Store marking guide in database
- [x] Update marking guide endpoint
- [x] Add/delete questions endpoints
- [x] Frontend: Editable marking guide table (question text, marks, type, answer guide)
- [x] Frontend: Answer guide textarea per question (`marking_guide.answer_scheme`)
- [x] Per-question **Keypoint marks** support (`marking_guide.keypoint_marks`)
- [x] Keypoint marks auto-save (no manual save button)
- [x] Visual indicator for unsaved Answer Guide edits

### Files Created:

- [x] `backend/routes/marking_guide.py` - Marking guide endpoints
- [x] `backend/schemas/marking_guide.py` - Marking guide schemas
- [x] `frontend/src/pages/GradePaper.jsx` - Includes marking guide editing

---

## Phase 7: Grade Paper - Step 4 (Grading)

- [x] LLM grading service that compares **cropped student answer text** with answer guide per question
- [x] Parse LLM responses into whole‑number scores, ignoring feedback text
- [x] Deterministic keypoint scoring using structured marking points and per-keypoint marks
- [x] Removed evidence-quote output/validation; grading relies on score + feedback only
- [x] Store grades with links to `student_answers` and `llm_responses`
- [x] Calculate totals per student and persist in `grading_summary`
- [x] Allow manual teacher override for each per‑question score and reflect it immediately in the UI
- [x] Update exam status (grading -> completed)
- [x] Frontend: Results page per exam with per‑question scores, student answers, and answer guides

### Files Created:

- [x] `backend/routes/grading.py` - Grading endpoints
- [x] `backend/schemas/grade.py` - Grade schemas

---

## Phase 8: Exam List & Results

- [x] List all exams with status endpoint
- [x] Get exam details with grades endpoint
- [x] Teacher override score endpoint
- [x] Frontend: Exam list page
- [x] Frontend: Progress indicator for grading exams
- [x] Frontend: View results page (per exam)
- [x] Frontend: Individual student grades view
- [x] Frontend: Score override functionality
- [x] Frontend: Custom delete exam modal (replaces browser confirm)
- [x] Frontend: Exam search + sort controls

### Files Created:

- [x] `frontend/src/pages/ExamList.jsx`
- [x] `frontend/src/pages/ExamResults.jsx`

---

## Phase 9: Manage Account

- [x] Get user profile endpoint
- [x] Update user profile endpoint
- [x] Change password endpoint
- [x] Delete account endpoint
- [x] Frontend: Account settings page
- [x] Upload/remove profile picture endpoints and UI
- [x] Profile picture crop modal before upload (zoom + reposition)
- [x] Cache-busting profile picture URL updates (instant refresh)
- [x] Custom delete-account modal (replaces browser confirm)
- [x] Navbar account behavior: Account tab opens page, user box opens Settings/Logout menu

### Files Created:

- [x] `backend/routes/account.py` - Account endpoints
- [x] `frontend/src/pages/ManageAccount.jsx`

---

## Phase 10: Reports

- [x] Excel summary export (openpyxl)
- [x] PDF per student export (reportlab)
- [x] Download endpoints
- [x] Download all PDFs as ZIP

### Files Created:

- [x] `backend/services/report_service.py` - Report generation
- [x] `backend/routes/reports.py` - Report endpoints

---

## Phase 11: Testing & Polish

- [x] Responsive design (TailwindCSS)
- [x] Error handling (all API calls)
- [x] Loading states (all async operations)
- [x] Form validation
- [x] End-to-end testing with real exam papers
- [x] Browser compatibility testing
- [x] Delete exam now removes uploaded files/folders from disk (`uploads/<exam_id>`)
- [x] CRAFT detector thresholds made configurable via environment variables

---

## Phase 12: Model lifecycle, LLM/OCR refinements & UI

### Backend / OCR / LLM

- [x] Centralize TrOCR loading in `model_loader.py`; preload model on FastAPI lifespan startup (`main.py`)
- [x] Local Ollama grading: resolve chat model via `get_ollama_model()` / `OLLAMA_MODEL` from environment (no stale client-side override)
- [x] Grading logprobs: Ollama + OpenRouter request completion logprobs; lexical confidence = **geometric mean** of token probs `exp(mean(logprob))`, clamped; HTTP 400 → retry without logprobs; persist `grades.confidence`; expose in grade APIs, ExamResults, student PDF
- [x] Optional Ollama **vision** pass for student-answer OCR refresh (config e.g. `OLLAMA_VISION_MODEL`, JSON `corrected_text`, image resize, error handling; `use_ollama_vision` query param where applicable)
- [x] `processing.py`: re-raise `HTTPException` before generic `except` so clients get correct status codes (e.g. 502 vs 500)

### Grade Paper / marking workflow (frontend)

- [x] Marking guide: yellow border / focus ring for **unsaved** answer guide edits; avoid clashing blue focus on that state
- [x] Crop modal: sticky **Extracted Text** header while scrolling region list
- [x] Question type `<select>` uses `q.question_type || 'structured'` only (removed `normalizeQuestionType` indirection)
- [x] Process step: student document row — outer control is `div role="button"` + keyboard handling; inner delete remains a real `<button>` (fixes invalid nested buttons)

### Chrome & theme

- [x] Navbar: frosted / semi-transparent background when scrolled (`backdrop-blur`, layered opacity)
- [x] **Dark mode**: Tailwind `darkMode: 'class'`; `ThemeProvider` + `localStorage` key `utar-grader-theme`; `ThemeToggle` in Navbar and on Login/Register
- [x] `index.html` inline script applies `html.dark` before paint to reduce flash
- [x] Global dark styles in `index.css` (cards, inputs, tables, drop zones, badges, auth shell, scrollbars)
- [x] Page-level dark pass: `Dashboard`, `GradePaper`, `ExamList`, `ExamResults`, `ManageAccount`, auth pages, loading spinner in `App.jsx`
- [x] Dark mode readability: marking guide footer — **“N questions”** and **“Total: … marks”** pill (slate chip + high-contrast text; no light-on-white)

### Housekeeping & dead code (safe removals)

- [x] Audit unused Python/JS helpers (grep + vulture-style review); documented larger optional deletions (e.g. unused `PDFService` methods) without removing live API routes
- [x] `processing.py`: drop unused `base64` / `subprocess` imports; `for region in regions` in background OCR loop (no unused index)
- [x] `schemas/marking_guide.py` + `routes/marking_guide.py`: remove unused `MarkingGuideListResponse`
- [x] `frontend/src/services/api.js`: remove unused wrappers — `authAPI.logout`, `processingAPI.processExam` / `detectRegions` / `checkOCRHealth` / `checkLLMHealth`, `gradingAPI.getStudentGrades` / `getProgress` (backend endpoints unchanged; re-add client helpers if UI needs them)

### Files touched (high level)

- [x] `backend/main.py`, `backend/model_loader.py`, `backend/config.py`
- [x] `backend/services/ocr_service.py`, `backend/services/llm_service.py`
- [x] `backend/routes/processing.py`, `backend/routes/grading.py` (as needed for above features)
- [x] `frontend/tailwind.config.js`, `frontend/index.html`, `frontend/src/main.jsx`
- [x] `frontend/src/context/ThemeContext.jsx`, `frontend/src/components/ThemeToggle.jsx`
- [x] `frontend/src/components/Navbar.jsx`, `frontend/src/index.css`
- [x] `frontend/src/pages/GradePaper.jsx`, `ExamList.jsx`, `ExamResults.jsx`, `ManageAccount.jsx`, `Login.jsx`, `Register.jsx`, `Dashboard.jsx`, `App.jsx`

---

## Frontend Files Created

- [x] `frontend/package.json` - Dependencies
- [x] `frontend/vite.config.js` - Vite configuration
- [x] `frontend/tailwind.config.js` - Tailwind CSS
- [x] `frontend/index.html` - Entry HTML
- [x] `frontend/src/main.jsx` - React entry point
- [x] `frontend/src/App.jsx` - Main app with routing
- [x] `frontend/src/index.css` - Global styles
- [x] `frontend/src/context/AuthContext.jsx` - Auth state
- [x] `frontend/src/services/api.js` - API client
- [x] `frontend/src/components/Navbar.jsx` - Navigation
- [x] `frontend/src/pages/Login.jsx` - Login page
- [x] `frontend/src/pages/Register.jsx` - Register page
- [x] `frontend/src/pages/Dashboard.jsx` - Dashboard layout
- [x] `frontend/src/pages/GradePaper.jsx` - 4-step grading wizard
- [x] `frontend/src/pages/ExamList.jsx` - Exam list
- [x] `frontend/src/pages/ExamResults.jsx` - Results view
- [x] `frontend/src/pages/ManageAccount.jsx` - Account settings
- [x] `frontend/src/context/ThemeContext.jsx` - Light/dark theme + persistence
- [x] `frontend/src/components/ThemeToggle.jsx` - Sun/moon toggle control

---

## Database Tables Summary

| Table             | Purpose                                                        |
| ----------------- | -------------------------------------------------------------- |
| `users`           | Teacher accounts                                               |
| `exams`           | Exam sessions                                                  |
| `documents`       | Uploaded PDFs (question paper, answer scheme, student answers) |
| `extracted_text`  | OCR results per region                                         |
| `marking_guide`   | Question templates with expected answers and marks             |
| `llm_responses`   | All LLM interactions for audit                                 |
| `student_answers` | Mapped student answers to questions                            |
| `grades`          | Scores and feedback per answer                                 |
| `grading_summary` | Total scores per student                                       |

---

## API Endpoints Summary

### Authentication

| Method | Endpoint             | Description          |
| ------ | -------------------- | -------------------- |
| POST   | `/api/auth/register` | Register new teacher |
| POST   | `/api/auth/login`    | Login, return JWT    |
| GET    | `/api/auth/me`       | Get current user     |

### Exams

| Method | Endpoint          | Description       |
| ------ | ----------------- | ----------------- |
| POST   | `/api/exams`      | Create exam       |
| GET    | `/api/exams`      | List user's exams |
| GET    | `/api/exams/{id}` | Get exam details  |
| DELETE | `/api/exams/{id}` | Delete exam       |

### Documents

| Method | Endpoint                    | Description       |
| ------ | --------------------------- | ----------------- |
| POST   | `/api/exams/{id}/upload`    | Upload PDF        |
| GET    | `/api/documents/{id}/pages` | Get PDF as images |
| POST   | `/api/documents/{id}/crop`  | Save crop region  |

### Processing

| Method | Endpoint                         | Description          |
| ------ | -------------------------------- | -------------------- |
| POST   | `/api/exams/{id}/process`        | Start OCR processing |
| GET    | `/api/exams/{id}/extracted-text` | Get extracted text   |
| POST   | `/api/regions/{id}/ocr`          | Run OCR on region    |

### Marking Guide

| Method | Endpoint                         | Description            |
| ------ | -------------------------------- | ---------------------- |
| POST   | `/api/exams/{id}/generate-guide` | Generate marking guide |
| GET    | `/api/exams/{id}/marking-guide`  | Get marking guide      |
| PUT    | `/api/marking-guide/{id}`        | Update question        |
| DELETE | `/api/marking-guide/{id}`        | Delete question        |
| POST   | `/api/exams/{id}/marking-guide`  | Add question           |

### Grading

| Method | Endpoint                 | Description    |
| ------ | ------------------------ | -------------- |
| POST   | `/api/exams/{id}/grade`  | Start grading  |
| GET    | `/api/exams/{id}/grades` | Get all grades |
| PUT    | `/api/grades/{id}`       | Override score |

### Reports

| Method | Endpoint                         | Description          |
| ------ | -------------------------------- | -------------------- |
| GET    | `/api/exams/{id}/report/excel`   | Download Excel       |
| GET    | `/api/documents/{id}/report/pdf` | Download student PDF |

### Account

| Method | Endpoint                | Description     |
| ------ | ----------------------- | --------------- |
| GET    | `/api/account`          | Get profile     |
| PUT    | `/api/account`          | Update profile  |
| POST   | `/api/account/profile-picture` | Upload/replace profile picture |
| DELETE | `/api/account/profile-picture` | Remove current profile picture |
| PUT    | `/api/account/password` | Change password |
| DELETE | `/api/account`          | Delete account  |

---

## Current Progress

**Status**: Core product phases (1–11) complete. Phase 12 adds model preload, Ollama/env-driven grading model, optional vision OCR assist, HTTP error correctness, marking-guide/crop UX, accessible document rows, full **dark mode**, and contrast fixes.
**Last Updated**: 2026-04-17

### Priority TODOs

- [x] Use Ollama (local model) to run spelling/grammar cleanup specifically for extracted **question text**
  - Acceptance: cleanup can run immediately after extraction and persists cleaned text back to region/question rows.
- [x] Fine-tune CRAFT detection for handwritten head/tail misses
  - Acceptance: add tunable presets/controls for thresholds and verify improved line coverage on difficult samples.
- [x] TrOCR preload on API startup; centralized model loader
- [x] Dark mode (class strategy, persistence, main surfaces + marking guide contrast)
- [x] Optional Ollama vision for student OCR refresh (env-driven model; API behavior documented in code/config)
- [x] Rebuild `captureAPI` methods in frontend service layer
- [x] Reimplement capture session/page/finalize endpoints in `backend/routes/documents.py`
- [x] Rebuild `CaptureSession` with jscanify live edge preview + one-row gallery + retake/delete + confirm flow
- [x] Reconnect `GradePaper` QR launch flow and desktop refresh behavior without auto-jumping to process step
- [x] Validate capture flow compile/syntax checks (`npm run build`, `python -m compileall backend/routes/documents.py`)
- [x] Simplify phone capture to photo-first flow (no scan processing on tap; server finalize after confirm)
- [x] Show phone-captured docs in Upload cards and apply jscanify processing at confirm stage
- [x] Move capture processing fully to laptop/server finalize (phone capture-only)
- [x] Improve server image pipeline with auto deskew (minAreaRect) + Otsu contour crop
- [x] Strengthen server capture scan with Hough-line deskew + quad warp + tighter crop
- [x] Align server warp step to reference contour code (bilateral + Canny10/20 + biggest quad + A4)
- [x] Return per-page processing status to phone gallery (red border fallback + full-image modal actions)
- [x] Fix gallery status misclassification and add binary black/white page output for OCR
- [x] Add tap-to-focus on phone camera
- [x] Switch processed capture output to grayscale for preview and generated PDF
- [x] Detect contour on downscaled image but warp/crop using original-resolution image to reduce blur
- [x] Force red border status when largest contour is not found (`fallback-no-contour`)
- [x] Add cancel-retake action and move capture control to centered bottom camera button
- [x] For student-answer scans, prompt after successful PDF upload to capture another or exit
- [x] Sync desktop QR auto-refresh with phone "capture another" continuation session
- [x] Close desktop QR panel when phone user exits student-answer capture chain
- [x] In Process stage, allow adding student answers via Upload Local and Scan QR actions
- [x] Ignore tiny crop regions and skip OCR/processing for accidental small drags
- [x] Reload page after confirming new cropped profile picture upload
- [x] Remove `users.profile_picture_version` column and migrate existing SQLite schema
- [x] Rename `users.password_hash` column to `password` and update auth/account usage
- [x] Rename `users.profile_picture_data` to `profile_picture` and remove mime column
- [x] Simplify account route profile-picture extension validation constants
- [x] Allow GIF uploads for profile picture input
- [x] Rename grading report bundle service module to `grading_report_bundle_service.py`

### Next Steps

1. Run repeatable sample-based validation for CRAFT presets on your exam set
2. Record baseline vs tuned OCR examples (missed heads/tails) for regression evidence
3. Validate `OLLAMA_MODEL` / optional vision env vars in staging (latency, GPU/RAM)
4. Prepare deployment checklist and production environment validation
