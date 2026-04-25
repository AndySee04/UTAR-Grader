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
- [x] Email verification at registration (`users.email_verified`, JWT link; idempotent verify; grading-style email template); SMTP required
- [x] Forgot / reset password (`POST /auth/forgot-password`, `POST /auth/reset-password`; JWT; email matches verification layout)

### Files Created:

- [x] `backend/utils/auth.py` - Password hashing, JWT utilities
- [x] `backend/routes/auth.py` - Auth endpoints
- [x] `backend/schemas/auth.py` - Pydantic schemas for auth
- [x] `users.email_verified` — verification state on user row; signed JWT verify links (no pending table)
- [x] `frontend/src/pages/Login.jsx`
- [x] `frontend/src/pages/Register.jsx`
- [x] `frontend/src/pages/VerifyEmail.jsx`
- [x] `frontend/src/pages/ForgotPassword.jsx`
- [x] `frontend/src/pages/ResetPassword.jsx`
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

- [x] Audit unused Python/JS helpers (grep + vulture-style review); documented larger optional deletions (e.g. unused `PDFService` methods); unused **HTTP routes** later removed (see *Removed API routes* under API Endpoints Summary)
- [x] `processing.py`: drop unused `base64` / `subprocess` imports; `for region in regions` in background OCR loop (no unused index)
- [x] `schemas/marking_guide.py` + `routes/marking_guide.py`: remove unused `MarkingGuideListResponse`
- [x] `frontend/src/services/api.js`: removed unused client wrappers (no `logout`, `processExam`, `detectRegions`, health checks, per-student grades GET, progress); **backend** unused routes removed to match (see API Endpoints Summary — *Removed API routes*).

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

Routes match the **current** FastAPI app (`backend/main.py` prefixes). Path parameters use names like `{exam_id}`, `{document_id}`, `{session_id}`, `{guide_id}`, `{region_id}`, `{grade_id}`, `{page_id}`.

The **Task / when used** column ties each route to a **concrete action** in the current web app (`frontend/src`), so it is clear *why* the endpoint exists. If an endpoint is infrastructure-only, that is stated.

### Core

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| GET | `/` | Smoke check: confirms the API process is up (message JSON). |
| GET | `/health` | Liveness/readiness style check; not tied to a specific UI button. |

### Authentication

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| POST | `/api/auth/register` | **Register** — submit new teacher account on the Register page. |
| POST | `/api/auth/login` | **Sign in** — submit email/password on Login; returns JWT for subsequent requests. |
| GET | `/api/auth/me` | **Who am I** — after login or on app load, load current user (name, email, profile picture URL). |

### Exams

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| POST | `/api/exams` | **Create exam** — start a new exam session from the grading flow (new exam name). |
| GET | `/api/exams` | **List exams** — populate the Exam List page (names, status, links to grade/results). |
| GET | `/api/exams/{exam_id}` | **Load one exam** — open Grade Paper for that exam; refresh status while polling (e.g. after processing). |
| PUT | `/api/exams/{exam_id}` | **Rename exam** — inline rename on Exam List. |
| DELETE | `/api/exams/{exam_id}` | **Delete exam** — remove exam and related data from Exam List. |

### Documents & capture sessions

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| POST | `/api/exams/{exam_id}/upload` | **Upload one PDF** — question paper, answer scheme, or a single student script. |
| POST | `/api/exams/{exam_id}/upload-multiple` | **Upload many student PDFs** — batch student answer uploads. |
| GET | `/api/exams/{exam_id}/documents` | **List documents** — show uploaded files per type (`question_paper`, `answer_scheme`, `student_answer`). |
| DELETE | `/api/{document_id}` | **Remove a document** — delete one uploaded PDF from the exam. |
| PATCH | `/api/{document_id}` | **Rename student answer** — update display `file_name` (`.pdf` or `.zip` to match upload) on Process Documents step. |
| POST | `/api/{document_id}/crop` | **Save a crop** — after drawing a region on a page, store its bounding box (manual crop; no auto-detect in UI). |
| GET | `/api/{document_id}/regions` | **List regions** — load all saved crops/OCR regions for that document (cropping UI, rebuild marking guide from question regions). |
| PUT | `/api/{document_id}/regions/order` | **Reorder regions** — persist order of answer regions (e.g. per page). |
| POST | `/api/exams/{exam_id}/capture-sessions` | **Start phone capture** — create a session and QR/link for capturing pages on a phone. |
| GET | `/api/exams/{exam_id}/capture-sessions/{session_id}` | **Owner: session status** — desktop checks session state while phone is capturing. |
| GET | `/api/capture-sessions/{session_id}` | **Public: session** — phone loads session using `token` query (no Bearer auth on this route as implemented). |
| GET | `/api/capture-sessions/{session_id}/pages` | **Public: list pages** — phone gallery lists captured pages (`token` query). |
| POST | `/api/capture-sessions/{session_id}/pages` | **Public: upload page** — phone posts a new photo/PDF page (`token` in form). |
| GET | `/api/capture-sessions/{session_id}/pages/{page_id}/image` | **View page image** — preview thumbnail/full image for a captured page. |
| DELETE | `/api/capture-sessions/{session_id}/pages/{page_id}` | **Delete a page** — retake/remove one page from the session. |
| POST | `/api/capture-sessions/{session_id}/finalize` | **Finalize capture** — merge pages into a PDF on the server; body includes `token`, `page_ids`, and for **student_answer** sessions a required `file_name` (student name / display file name). |
| POST | `/api/capture-sessions/{session_id}/continue` | **Continue** — move to “next student” capture while keeping the same exam (multi-student flow). |
| POST | `/api/capture-sessions/{session_id}/exit` | **Exit session** — end phone capture without finalizing (cleanup signal). |

### Processing (pages, OCR, regions)

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| GET | `/api/documents/{document_id}/pages` | **Page metadata** — list pages with dimensions for the crop viewer. |
| GET | `/api/documents/{document_id}/pages/{page_number}/image` | **Render page** — fetch PNG for display while cropping or viewing. |
| POST | `/api/regions/{region_id}/ocr` | **Run OCR** — extract text from a cropped region (after save crop or refresh). |
| PATCH | `/api/regions/{region_id}` | **Edit region** — save edited OCR text, question number, marks; optional sync to student regions. |
| DELETE | `/api/regions/{region_id}` | **Delete region** — remove one crop/region row. |
| POST | `/api/regions/{region_id}/cleanup` | **LLM cleanup** — optional spelling/grammar cleanup of OCR text for a region. |

### Marking guide

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| GET | `/api/exams/{exam_id}/marking-guide` | **Load all questions** — fill the marking guide editor; also read before rebuild in “Process documents”. |
| POST | `/api/exams/{exam_id}/marking-guide` | **Add question** — create one marking-guide row (manual add, or after process builds rows from crops). |
| PUT | `/api/marking-guide/{guide_id}` | **Edit question** — update fields (text, marks, scheme, etc.) inline in the guide table. |
| DELETE | `/api/marking-guide/{guide_id}` | **Remove one question row** — in the current app, called in a loop when **Process documents** rebuilds the guide: delete **all** existing questions first, then `POST` new rows from cropped question-paper regions (preserves scheme text by question number where possible). |

### Grading

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| POST | `/api/exams/{exam_id}/grade` | **Start grading** — enqueue/run automatic grading for all student scripts for this exam. |
| GET | `/api/exams/{exam_id}/grades` | **Results overview** — load all students’ scores and per-question breakdown for Exam Results. |
| PUT | `/api/grades/{grade_id}` | **Override score** — teacher edits a mark after auto-grading (Exam Results). |

### Reports

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| GET | `/api/exams/{exam_id}/report/excel` | **Export Excel** — download spreadsheet of results (Exam List). |
| GET | `/api/exams/{exam_id}/report/pdf/{document_id}` | **One student PDF** — download report for one student (Exam Results). |
| GET | `/api/exams/{exam_id}/report/all-pdfs` | **Zip all PDFs** — bulk download reports (Exam List). |

### Account

| Method | Endpoint | Task / when used |
| ------ | -------- | ------------------ |
| GET | `/api/account` | **Load profile** — Manage Account page. |
| PUT | `/api/account` | **Update name** — save display name. |
| POST | `/api/account/profile-picture` | **Upload avatar** — set profile picture file. |
| DELETE | `/api/account/profile-picture` | **Remove avatar** — clear profile picture. |
| GET | `/api/account/profile-picture/{user_id}` | **Show avatar image** — `img src` URL returned in `/me`; browser loads the image bytes. |
| PUT | `/api/account/password` | **Change password** — authenticated password change form. |
| DELETE | `/api/account` | **Delete account** — remove teacher account and sign out. |

### Removed API routes (reference)

These endpoints were removed from the backend as unused by the current web client (`frontend/src` + `CaptureSession.jsx`). Restore from git history if a future client needs them.

| Method | Endpoint | Former purpose |
| ------ | -------- | ---------------- |
| POST | `/api/auth/logout` | Ack logout (JWT discarded client-side only) |
| GET | `/api/{document_id}` | Get single document metadata |
| POST | `/api/documents/{document_id}/detect-regions` | CV auto-detect regions (unused; UI uses manual crop) |
| POST | `/api/exams/{exam_id}/process` | Background auto-detect + OCR for exam docs (never called by UI) |
| GET | `/api/health/ocr` | OCR service health |
| GET | `/api/health/llm` | LLM service health |
| POST | `/api/exams/{exam_id}/generate-guide` | LLM-based guide generation (retired; DB-driven process flow now authoritative) |
| GET | `/api/marking-guide/{guide_id}` | Get one marking-guide row |
| GET | `/api/exams/{exam_id}/grades/{document_id}` | Grades for one student document |
| GET | `/api/exams/{exam_id}/progress` | Grading progress counts |

---

## Current Progress

**Status**: Core product phases (1–11) complete. Phase 12 adds model preload, Ollama/env-driven grading model, optional vision OCR assist, HTTP error correctness, marking-guide/crop UX, accessible document rows, full **dark mode**, and contrast fixes.
**Last Updated**: 2026-04-25

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
- [x] Require full name during registration (frontend + backend validation)
- [x] Use direct `name.trim()` checks (no temporary name variable)
- [x] Add explicit invalid-email handling in auth forms (register/login/forgot password)
- [x] Rename crop cleanup helper to `cleanupQuestionRegionText` for clarity
- [x] Rename question cleanup toggle state to `questionCleanupEnabled`
- [x] Remove LLM marking-guide generation path (`/generate-guide`) and keep DB-only guide flow
- [x] Persist grading audit metadata (`prompt_used`, `tokens_used`) in `llm_responses`
- [x] Standardize `llm_responses.model_used` format to `provider:model` for cleanup + grading

### Next Steps

1. Run repeatable sample-based validation for CRAFT presets on your exam set
2. Record baseline vs tuned OCR examples (missed heads/tails) for regression evidence
3. Validate `OLLAMA_MODEL` / optional vision env vars in staging (latency, GPU/RAM)
4. Prepare deployment checklist and production environment validation
