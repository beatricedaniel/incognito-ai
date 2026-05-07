---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
status: complete
completedAt: '2026-05-03'
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/architecture.md"
---

# incognito-ai - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for incognito-ai, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can drag-and-drop a PDF file onto the application window to begin processing
FR2: User can select a PDF file via a file picker dialog as an alternative to drag-and-drop
FR3: System extracts text per block (paragraph/line) from each page of an uploaded PDF, preserving the bounding box of each block as returned by PyMuPDF
FR4: System rejects non-PDF files with a clear error message
FR5: System rejects unsupported PDF types (encrypted, scanned/image-only) with a clear error message
FR6: System detects person names in extracted PDF text using Gemma 4 E4B via Ollama, processing per-block to preserve bounding box alignment
FR7: System detects physical addresses in extracted PDF text using Gemma 4 E4B via Ollama
FR8: System detects phone numbers in extracted PDF text using Gemma 4 E4B via Ollama
FR9: System detects email addresses in extracted PDF text using Gemma 4 E4B via Ollama
FR10: System inherits bounding box coordinates from the source text block for each detection
FR10a: System validates every detection post-inference: the detected entity text must exist verbatim at the claimed start:end offsets within the source block. Detections that fail validation are silently dropped.
FR11: System provides processing feedback during detection (simple spinner/status text)
FR12: User can view a rendered preview of the uploaded PDF alongside a sidebar list of detected PII entities (grouped by page, showing entity type and text snippet)
FR13: User can distinguish PII entity types in the sidebar list via text labels and optional color badges (person, address, phone, email)
FR14: User can dismiss a false-positive detection from the sidebar list (removes it before redaction)
FR15: User can see a summary of detected entities (count per entity type) at the top of the sidebar
FR16: System displays an AI limitation disclaimer advising the user to review all detections carefully
FR17: User can trigger redaction of all confirmed (non-dismissed) PII entities
FR18: System permanently removes confirmed PII text from the PDF data layer (true redaction)
FR19: System renders black bars over redacted areas in the visual layer of the output PDF
FR20: System strips PDF metadata (Author, Title, Subject, Creator, Producer) from the redacted output
FR21: System strips XMP metadata from the redacted output
FR22: System performs garbage collection to remove orphaned objects from the redacted output
FR23: System saves the redacted PDF as a non-incremental write (no prior document versions preserved)
FR24: System saves the redacted PDF as a new file with `_redacted` suffix, leaving the original untouched
FR25: System writes intermediate processing files to a secure OS temporary directory
FR26: System deletes all temporary files immediately after producing the redacted output
FR27: System scans for and deletes orphaned temporary files on launch (crash recovery)
FR28: System makes zero network calls during document processing
FR29: System checks whether Ollama is running and the Gemma 4 E4B model is loaded via GET /api/tags on 127.0.0.1:11434. Displays "Ready" or "Please start Ollama with Gemma 4 E4B" accordingly.
FR30: (Deferred to stretch) System starts Ollama as a subprocess if not running and triggers model download if missing.
FR31: System displays Ollama readiness status to the user (ready / not ready) on the main screen
FR32: (Deferred to stretch) Download progress during first-launch model pull.
FR33: (Deferred to stretch) Subprocess lifecycle management.
FR34: UI shows a "100% local — no data leaves your machine" badge on the main screen
FR35: User can launch the application from a localhost web interface opened in the default browser (MVP)
FR36: User can access the application immediately after the Ollama/model readiness check completes
FR37: System selects a random available port for the localhost web server to avoid conflicts
FR38: System includes an evaluation framework that measures precision, recall, and F1 per entity type against ground-truth annotated test documents
FR39: System includes an automated redaction verification test that extracts text from redacted output and asserts zero PII matches
FR40: Evaluation framework covers at least 5 test documents with French-language PII

### NonFunctional Requirements

NFR1: Single-page PDF completes the full pipeline (text extraction + per-block PII detection + validation + result display) in under 30 seconds on a machine with 8 GB RAM and no GPU
NFR2: 10-page PDF completes the full pipeline in under 3 minutes under the same conditions
NFR3: UI remains responsive during processing — no frozen screen. A spinner with status text keeps the user informed.
NFR4: (Deferred) Ollama cold start management. MVP assumes Ollama is already running with model loaded.
NFR5: Redaction operation (apply_redactions + sanitization + save) completes in under 5 seconds for a 10-page document
NFR6: Application startup (FastAPI server + browser open + Ollama readiness check) completes in under 5 seconds when Ollama is already running
NFR7: Zero network calls during the entire document processing pipeline. Verifiable via network traffic monitoring.
NFR8: No PII from processed documents is written to persistent storage except in the user-requested redacted output file.
NFR9: Redacted output contains zero extractable PII — verified by pdftotext text extraction, PDF metadata fields, and XMP metadata absent
NFR10: No telemetry, analytics, crash reporting, or usage logging that captures document content or PII
NFR11: Temp files use OS-level restricted permissions (owner-only read/write) during processing
NFR12: Orphaned temp files from prior crashes are detected and deleted on application launch
NFR13: Web interface follows basic semantic HTML structure for screen reader compatibility
NFR14: All interactive elements are keyboard-navigable (upload, review, dismiss, redact)
NFR15: Color-coded highlights are supplemented with text labels so entity type information is not conveyed by color alone
NFR16: UI text meets WCAG 2.1 AA contrast ratio (4.5:1 minimum for normal text)

### Additional Requirements

- Starter template: `uv init` + purpose-built scaffold — first implementation story must initialize project structure
- `import-linter` enforces layered architecture boundaries mechanically (static/ → api/ → pipeline/ → ollama/ → core/)
- `pytest-socket` blocks all non-localhost connections in test suite by default
- Pipeline modules (`pipeline/`) are synchronous pure functions — no async/await
- `detector.py` calls Ollama exclusively through `ollama/manager.py` — never imports HTTP clients directly
- Session state: server-side in-memory dictionary keyed by session ID, with 30-minute timeout cleanup
- PDF.js vendored locally in `static/js/vendor/pdfjs/` — no CDN dependency at runtime
- SSE uses exactly 3 event types: `stage_update`, `pipeline_error`, `pipeline_complete`
- Typed exception hierarchy in `core/exceptions.py`: IncognitoError → PdfError, DetectionError, RedactionError, OllamaError, SessionError
- Frontend state machine: idle → uploading → processing → reviewing → redacting → complete (any → error, error/complete → idle)
- `python -m incognito` is the canonical entry point (via `__main__.py`)
- Python `logging` to stderr only — never log document content, filenames, or PII
- Ruff rule sets: E, F, W, I, N, UP, S, B, A, C4, C90, PT, ANN, SIM, TID, PL, RUF
- mypy --strict passes on all source code
- Supply chain security: cyclonedx-bom for SBOM + pip-audit --strict in CI
- Property-based testing via hypothesis for privacy invariants
- Snapshot testing via syrupy for redaction metadata serialization

### UX Design Requirements

N/A — No UX Design document found. Frontend requirements are captured in the PRD (FR12-16) and Architecture (frontend state machine, sidebar list, PDF.js static preview).

### FR Coverage Map

FR1: Epic 2 — Drag-and-drop PDF input
FR2: Epic 2 — File picker PDF input
FR3: Epic 2 — Per-block text extraction with bounding boxes
FR4: Epic 2 — Reject non-PDF files
FR5: Epic 2 — Reject encrypted/scanned PDFs
FR6: Epic 3 — Detect person names via Gemma 4 E4B
FR7: Epic 3 — Detect physical addresses via Gemma 4 E4B
FR8: Epic 3 — Detect phone numbers via Gemma 4 E4B
FR9: Epic 3 — Detect email addresses via Gemma 4 E4B
FR10: Epic 3 — Inherit bounding box from source text block
FR10a: Epic 3 — Post-detection validation (verify offsets match source)
FR11: Epic 3 — Processing feedback (spinner/status text)
FR12: Epic 4 — PDF preview + sidebar detection list
FR13: Epic 4 — Entity type badges in sidebar
FR14: Epic 4 — Dismiss false-positive detections
FR15: Epic 4 — Entity count summary
FR16: Epic 4 — AI limitation disclaimer
FR17: Epic 5 — Trigger redaction of confirmed entities
FR18: Epic 5 — True redaction (permanent PII removal from data layer)
FR19: Epic 5 — Black bars over redacted areas
FR20: Epic 5 — Strip PDF metadata
FR21: Epic 5 — Strip XMP metadata
FR22: Epic 5 — Garbage collection (remove orphaned objects)
FR23: Epic 5 — Non-incremental save
FR24: Epic 5 — Save as new file with _redacted suffix
FR25: Epic 2 — Secure temp directory for intermediate files
FR26: Epic 5 — Delete temp files after redaction
FR27: Epic 1 — Orphaned temp file cleanup on launch
FR28: Epic 3 — Zero network calls during processing
FR29: Epic 1 — Ollama readiness check
FR30: Deferred (stretch) — Ollama subprocess management
FR31: Epic 1 — Display Ollama readiness status
FR32: Deferred (stretch) — Model download progress
FR33: Deferred (stretch) — Subprocess lifecycle management
FR34: Epic 1 — "100% local" badge
FR35: Epic 1 — Localhost web interface launch
FR36: Epic 1 — Immediate access after readiness check
FR37: Epic 1 — Random available port selection
FR38: Epic 6 — F1 evaluation framework
FR39: Epic 6 — Automated redaction verification test
FR40: Epic 6 — 5+ French-language test documents

## Epic List

### Epic 1: Project Foundation & App Shell
User can launch the app in their browser and see that the system is ready to process documents — Ollama status, "100% local" badge, and a clean drop zone. Includes project scaffold, core modules (config, exceptions, tempfiles, sessions), entry point, FastAPI app factory, and Ollama readiness check.
**FRs covered:** FR27, FR29, FR31, FR34, FR35, FR36, FR37

### Epic 2: PDF Input & Text Extraction
User can upload a PDF (drag-and-drop or file picker), and the system extracts text content per block with bounding boxes — or rejects invalid files with a clear message.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR25

### Epic 3: PII Detection & Validation
System automatically finds person names, addresses, phone numbers, and email addresses in the uploaded PDF, with a spinner showing progress — and silently drops any hallucinated detections. Zero-network enforcement verified.
**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR10a, FR11, FR28

### Epic 4: Detection Review & Human-in-the-Loop
User sees a PDF preview alongside a sidebar listing all detected PII (grouped by page, with type badges and counts), can dismiss false positives, and is reminded to review carefully.
**FRs covered:** FR12, FR13, FR14, FR15, FR16

### Epic 5: True Redaction & Secure Output
User clicks "Redact" and receives a new PDF with all confirmed PII permanently deleted from the data layer, metadata stripped, and the original file untouched. All temp files cleaned up.
**FRs covered:** FR17, FR18, FR19, FR20, FR21, FR22, FR23, FR24, FR26

### Epic 6: Evaluation Framework & Verification
Developers and hackathon reviewers can verify detection accuracy via per-entity-type F1 metrics and confirm redaction completeness via automated pdftotext verification on test documents.
**FRs covered:** FR38, FR39, FR40

---

## Epic 1: Project Foundation & App Shell

User can launch the app in their browser and see that the system is ready to process documents — Ollama status, "100% local" badge, and a clean drop zone.

### Story 1.1: Project Scaffold & Dev Tooling

As a developer,
I want a fully configured project structure with all dependencies, linting, and test tooling,
So that I can begin implementing features with consistent quality gates from day one.

**Acceptance Criteria:**

**Given** a clean checkout of the repository
**When** I run `uv sync`
**Then** all dependencies (runtime and dev) are installed and `uv.lock` is committed

**Given** the project is set up
**When** I run `ruff check src/ tests/`
**Then** zero violations are reported (rule sets E, F, W, I, N, UP, S, B, A, C4, C90, PT, ANN, SIM, TID, PL, RUF; line-length 100)

**Given** the project is set up
**When** I run `mypy --strict src/`
**Then** zero errors are reported

**Given** the project is set up
**When** I run `pytest`
**Then** the test suite passes (even if no tests exist yet, the runner succeeds)

**Given** the directory structure
**When** I inspect `src/incognito/`
**Then** subdirectories `api/`, `core/`, `pipeline/`, `ollama/`, `static/` exist with `__init__.py` files, and `__main__.py` exists at package root

### Story 1.2: Core Modules — Config, Exceptions, TempFileManager, Sessions

As a developer,
I want foundational core modules (config, typed exceptions, secure temp file management, session store),
So that all downstream pipeline and API modules have consistent configuration, error handling, and state management.

**Acceptance Criteria:**

**Given** `core/config.py` exists
**When** I import it
**Then** it exposes typed constants: `OLLAMA_HOST`, `OLLAMA_PORT`, `MODEL_NAME`, `TEMP_PREFIX`, `SESSION_TIMEOUT`, `LOG_LEVEL` as `typing.Final` values

**Given** `core/exceptions.py` exists
**When** I inspect the module
**Then** it defines `IncognitoError` as the base, with subclasses `PdfError`, `DetectionError`, `RedactionError`, `OllamaError`, `SessionError`

**Given** `core/tempfiles.py` with `TempFileManager`
**When** I use it as a context manager
**Then** it creates a temp directory with `incognito-` prefix and `0o700` permissions, and deletes it on exit (FR25, NFR11)

**Given** the application launches
**When** `TempFileManager.cleanup_orphans()` is called
**Then** all `incognito-*` directories in the OS temp directory are deleted (FR27, NFR12)

**Given** `core/sessions.py` exists
**When** I create a session
**Then** it returns a unique session ID and stores the session in an in-memory dictionary with a 30-minute timeout

**Given** a session has exceeded its timeout
**When** the session store is cleaned
**Then** the expired session is removed

### Story 1.3: Ollama Readiness Check

As a user,
I want the app to check whether Ollama and Gemma 4 E4B are available on startup,
So that I know immediately whether the system is ready to process my documents.

**Acceptance Criteria:**

**Given** Ollama is running on `127.0.0.1:11434` with `gemma4:e4b` loaded
**When** `manager.check_ready()` is called
**Then** it returns `True` (FR29)

**Given** Ollama is not running or `gemma4:e4b` is not available
**When** `manager.check_ready()` is called
**Then** it returns `False` and raises no exception

**Given** the Ollama host is anything other than `127.0.0.1`
**When** the manager initializes
**Then** it raises `OllamaError` (enforces `OLLAMA_HOST=127.0.0.1`)

**Given** the `ollama/manager.py` module
**When** I inspect `pipeline/` imports
**Then** no pipeline module imports `httpx` or any HTTP client directly — only `ollama/manager.py` makes HTTP calls (FR28)

### Story 1.4: FastAPI App Shell & Startup Sequence

As a user,
I want the application to start a localhost web server and open my browser automatically,
So that I can access the app immediately without manual setup.

**Acceptance Criteria:**

**Given** Ollama is running
**When** I run `python -m incognito`
**Then** a FastAPI server starts on a random available port, the Ollama readiness check runs, and my default browser opens to the app URL (FR35, FR36, FR37)

**Given** the server is running
**When** I call `GET /api/status`
**Then** it returns JSON with Ollama readiness status (`{"ollama_ready": true/false, "model": "gemma4:e4b"}`) (FR29)

**Given** the app starts
**When** startup completes
**Then** total startup time (server + readiness check + browser open) is under 5 seconds when Ollama is already running (NFR6)

**Given** the FastAPI app
**When** any `IncognitoError` subclass is raised in a route
**Then** it is caught by the exception handler and returned as structured JSON (`{"error": "...", "detail": "..."}`) with appropriate HTTP status

### Story 1.5: Landing Page with Status & Drop Zone

As a user,
I want to see a clean landing page with Ollama status, a "100% local" badge, and a drop zone,
So that I know the app is ready and how to start processing a document.

**Acceptance Criteria:**

**Given** the app is running and Ollama is ready
**When** I load the landing page
**Then** I see a green "Ready" status badge and a "100% local — no data leaves your machine" badge (FR31, FR34)

**Given** the app is running and Ollama is NOT ready
**When** I load the landing page
**Then** I see a "Please start Ollama with Gemma 4 E4B" message instead of the Ready badge (FR31)

**Given** the landing page is loaded
**When** I inspect the page
**Then** I see a drop zone area ("Drop a PDF here") and the frontend is in `idle` state

**Given** the HTML markup
**When** I inspect for accessibility
**Then** the page uses semantic HTML (proper headings, labels), all elements are keyboard-navigable, and text meets WCAG AA contrast (NFR13, NFR14, NFR16)

## Epic 2: PDF Input & Text Extraction

User can upload a PDF (drag-and-drop or file picker), and the system extracts text content per block with bounding boxes — or rejects invalid files with a clear message.

### Story 2.1: PDF Upload API & Frontend Drop Zone

As a user,
I want to drag-and-drop a PDF or use a file picker to upload it,
So that I can begin processing my document.

**Acceptance Criteria:**

**Given** the app is in `idle` state
**When** I drag a PDF file onto the drop zone
**Then** the file is uploaded via `POST /api/upload`, a session is created, and the frontend transitions to `uploading` state (FR1)

**Given** the app is in `idle` state
**When** I click the drop zone and select a PDF via the file picker
**Then** the file is uploaded identically to drag-and-drop (FR2)

**Given** a PDF is uploaded
**When** the backend receives it
**Then** it creates a session, stores the PDF in a secure temp directory via `TempFileManager` (FR25), and returns `{"session_id": "..."}` with SSE endpoint URL

**Given** a session is created
**When** I connect to `GET /api/events/{session_id}`
**Then** I receive SSE events as the pipeline progresses

### Story 2.2: PDF Validation & Error Handling

As a user,
I want clear error messages when I upload an invalid file,
So that I understand what went wrong and what file types are supported.

**Acceptance Criteria:**

**Given** I drag a non-PDF file (e.g., `.docx`, `.png`, `.txt`) onto the drop zone
**When** the upload is processed
**Then** the system returns HTTP 400 with `{"error": "Invalid file type", "detail": "Only PDF files are supported"}` and the frontend shows the error and returns to `idle` (FR4)

**Given** I upload an encrypted/password-protected PDF
**When** the system attempts to open it with PyMuPDF
**Then** it returns HTTP 400 with `{"error": "Unsupported PDF", "detail": "Encrypted PDFs are not supported"}` and the frontend shows the error (FR5)

**Given** I upload a scanned/image-only PDF (no extractable text)
**When** the system extracts text blocks and finds zero text content
**Then** it returns HTTP 400 with `{"error": "Unsupported PDF", "detail": "This PDF contains no extractable text (scanned/image-only)"}` (FR5)

**Given** any validation error occurs
**When** the frontend displays the error
**Then** temp files for that failed session are cleaned up immediately

### Story 2.3: Per-Block Text Extraction with Bounding Boxes

As a user,
I want the system to extract text from my PDF preserving the position of each text block,
So that detected PII can be accurately located and redacted in the correct place.

**Acceptance Criteria:**

**Given** a valid PDF is uploaded
**When** `extractor.extract_blocks(pdf_path)` is called
**Then** it returns a `list[TextBlock]` where each block has `text`, `page` (0-indexed), `bbox` (x0, y0, x1, y1), and `block_index` (FR3)

**Given** a multi-page PDF
**When** text is extracted
**Then** blocks from all pages are returned in page order, with correct page numbers

**Given** a PDF with mixed content (text + images)
**When** text is extracted
**Then** only text blocks are returned; image blocks are skipped

**Given** extraction completes
**When** SSE events are checked
**Then** a `stage_update` event with `{"stage": "extracting", "message": "Extracting text from PDF…"}` was emitted (FR11 partial)

**Given** `pipeline/extractor.py`
**When** I inspect its imports
**Then** it imports no HTTP clients and makes no network calls — pure synchronous function

## Epic 3: PII Detection & Validation

System automatically finds person names, addresses, phone numbers, and email addresses in the uploaded PDF, with a spinner showing progress — and silently drops any hallucinated detections.

### Story 3.1: Ollama Inference Interface

As a developer,
I want `ollama/manager.py` to expose a `generate(prompt, system)` function that calls Gemma 4 E4B,
So that the detector can send NER prompts and receive structured responses.

**Acceptance Criteria:**

**Given** Ollama is running with `gemma4:e4b` loaded
**When** `manager.generate(prompt, system)` is called
**Then** it sends a POST to `127.0.0.1:11434/api/generate` with the model name, prompt, and system message, and returns the response text

**Given** Ollama is not running or returns an error
**When** `generate()` is called
**Then** it raises `OllamaError` with a descriptive message (never swallows the error)

**Given** `ollama/manager.py`
**When** I inspect the HTTP calls
**Then** all requests target `127.0.0.1:11434` exclusively — no other hosts (FR28)

**Given** the generate function
**When** called with any prompt
**Then** no document content, filenames, or PII appear in log output

### Story 3.2: Per-Block PII Detection via Gemma 4

As a user,
I want the system to automatically detect person names, addresses, phone numbers, and email addresses in my PDF,
So that I can review what PII exists before deciding to redact.

**Acceptance Criteria:**

**Given** a list of `TextBlock` objects from the extractor
**When** `detector.detect(blocks, generate_fn)` is called
**Then** each block's text is sent to Gemma 4 E4B with a NER prompt, and the function returns `list[RawDetection]` with `entity_type`, `text`, `start`, `end`, `page`, `bbox`, and `block_index` (FR6, FR7, FR8, FR9)

**Given** a detection is returned by Gemma 4
**When** the detection is created
**Then** its `bbox` is inherited directly from the source `TextBlock` — no separate coordinate mapping (FR10)

**Given** the NER prompt
**When** I inspect it
**Then** it instructs Gemma 4 to return JSON with entity type (`person`, `address`, `phone`, `email`), exact text span, and character offsets within the block

**Given** a block with no PII
**When** Gemma 4 returns an empty result
**Then** `detect()` returns no detections for that block (not a fabricated empty list via try/except)

**Given** Gemma 4 returns malformed JSON for a block
**When** the detector parses the response
**Then** it raises `DetectionError` — never silently returns an empty list

**Given** `pipeline/detector.py`
**When** I inspect its imports
**Then** it does not import `httpx` or any HTTP client — it receives the generate function as a dependency

### Story 3.3: Post-Detection Validation

As a user,
I want every detection to be verified against the source text,
So that hallucinated entities with wrong offsets are silently filtered out before I see them.

**Acceptance Criteria:**

**Given** a `RawDetection` with `start` and `end` offsets and a reference to its source block
**When** `validator.validate(raw_detections, blocks)` is called
**Then** it checks that `block.text[start:end] == detection.text` for each detection (FR10a)

**Given** a detection where `block.text[start:end]` does NOT match `detection.text`
**When** validation runs
**Then** that detection is dropped from the output list (silently, no error raised)

**Given** a detection where offsets match
**When** validation runs
**Then** a `Detection` model is returned with `id` (unique), `validated=True`, and `dismissed=False`

**Given** a list of 10 raw detections where 3 have hallucinated offsets
**When** validation completes
**Then** exactly 7 `Detection` objects are returned

### Story 3.4: Processing Feedback via SSE

As a user,
I want to see a spinner with status text while the system detects PII,
So that I know the app is working and hasn't frozen.

**Acceptance Criteria:**

**Given** the detection pipeline is running
**When** text extraction begins
**Then** a `stage_update` SSE event is emitted: `{"stage": "extracting", "message": "Extracting text from PDF…"}`

**Given** extraction is complete and detection begins
**When** blocks are sent to Gemma 4
**Then** a `stage_update` SSE event is emitted: `{"stage": "detecting", "message": "Detecting PII entities…"}`

**Given** detection is complete and validation begins
**When** the validator runs
**Then** a `stage_update` SSE event is emitted: `{"stage": "validating", "message": "Validating detections…"}`

**Given** the full pipeline completes successfully
**When** detections are stored in the session
**Then** a `pipeline_complete` SSE event is emitted: `{"session_id": "...", "total_detections": N}` and the frontend transitions from `processing` to `reviewing` (FR11)

**Given** any pipeline stage fails
**When** the error is caught by the API layer
**Then** a `pipeline_error` SSE event is emitted: `{"error": "...", "stage": "...", "detail": "..."}` and the frontend transitions to `error`

**Given** SSE is streaming
**When** I observe the frontend
**Then** the UI remains responsive with a spinner and the current stage message (NFR3)

## Epic 4: Detection Review & Human-in-the-Loop

User sees a PDF preview alongside a sidebar listing all detected PII (grouped by page, with type badges and counts), can dismiss false positives, and is reminded to review carefully.

### Story 4.1: PDF Preview & Detection List API

As a user,
I want to retrieve the list of detected PII entities for my uploaded document,
So that I can review what was found before deciding to redact.

**Acceptance Criteria:**

**Given** a session with completed detection
**When** I call `GET /api/detections/{session_id}`
**Then** it returns a JSON array of detections, each with `id`, `text`, `entity_type`, `page`, `start`, `end`, `bbox`, `dismissed` (FR12)

**Given** the detections response
**When** I inspect the ordering
**Then** detections are grouped by page number and ordered by position within the page

**Given** an invalid or expired session ID
**When** I call `GET /api/detections/{session_id}`
**Then** it returns HTTP 404 with `{"error": "Session not found"}`

### Story 4.2: PDF.js Static Preview

As a user,
I want to see a rendered preview of my uploaded PDF next to the detection sidebar,
So that I can visually locate detected entities by page number.

**Acceptance Criteria:**

**Given** the pipeline has completed and the frontend is in `reviewing` state
**When** the review screen renders
**Then** PDF.js renders all pages of the uploaded PDF as static `<canvas>` elements in the main content area (FR12)

**Given** PDF.js is loaded
**When** I inspect the script source
**Then** it loads from `static/js/vendor/pdfjs/` (vendored locally) — no CDN requests

**Given** a multi-page PDF
**When** I scroll the preview
**Then** all pages are visible and page numbers are labeled

### Story 4.3: Sidebar Detection List with Entity Badges & Summary

As a user,
I want to see all detected PII in a sidebar grouped by page, with entity type badges and a count summary,
So that I can quickly understand the scope of PII found and review each detection.

**Acceptance Criteria:**

**Given** detections are loaded
**When** the sidebar renders
**Then** each detection shows: entity type badge (person/address/phone/email), text snippet, and page number — grouped under page headings (FR12, FR13)

**Given** the sidebar
**When** I look at entity type badges
**Then** each type has a distinct color AND a text label (e.g., "Person", "Address") so information is not conveyed by color alone (FR13, NFR15)

**Given** detections are loaded
**When** the sidebar renders
**Then** a summary at the top shows count per entity type (e.g., "5 persons, 3 addresses, 2 phones, 1 email") (FR15)

**Given** the sidebar HTML
**When** I inspect for accessibility
**Then** it uses semantic markup (list elements, headings per page group), all items are keyboard-focusable, and text meets WCAG AA contrast (NFR13, NFR14, NFR16)

### Story 4.4: Dismiss False Positives

As a user,
I want to dismiss individual detections that are false positives,
So that only genuine PII is redacted from my document.

**Acceptance Criteria:**

**Given** a detection in the sidebar
**When** I click its dismiss button
**Then** a `DELETE /api/detections/{session_id}/{id}` request is sent, the detection is marked `dismissed=true` in the session, and it is visually removed or struck through in the sidebar (FR14)

**Given** I dismiss a detection
**When** the sidebar summary updates
**Then** the entity count decreases to reflect only non-dismissed detections

**Given** the dismiss button
**When** I navigate via keyboard
**Then** I can focus and activate it with Enter or Space (NFR14)

**Given** an already-dismissed detection ID
**When** I call `DELETE /api/detections/{session_id}/{id}` again
**Then** it returns success idempotently (no error)

### Story 4.5: AI Limitation Disclaimer

As a user,
I want to see a clear notice that AI detection may miss some entities,
So that I understand my responsibility to review all detections before redacting.

**Acceptance Criteria:**

**Given** the frontend is in `reviewing` state
**When** the review screen renders
**Then** a visible disclaimer is displayed: "AI detection may miss some entities. Review all detections carefully before redacting." (FR16)

**Given** the disclaimer
**When** I inspect its placement
**Then** it appears above or alongside the sidebar, not hidden behind a tooltip or collapsible section

**Given** the disclaimer text
**When** I check contrast
**Then** it meets WCAG AA contrast ratio (NFR16)

## Epic 5: True Redaction & Secure Output

User clicks "Redact" and receives a new PDF with all confirmed PII permanently deleted from the data layer, metadata stripped, and the original file untouched. All temp files cleaned up.

### Story 5.1: Redaction API & Frontend Trigger

As a user,
I want to click a "Redact" button after reviewing detections,
So that I can produce a clean version of my document with all confirmed PII removed.

**Acceptance Criteria:**

**Given** the frontend is in `reviewing` state with at least one non-dismissed detection
**When** I click the "Redact" button
**Then** a `POST /api/redact/{session_id}` request is sent and the frontend transitions to `redacting` state (FR17)

**Given** the redaction request
**When** the backend processes it
**Then** it passes only non-dismissed detections to `redactor.redact()` — dismissed detections are excluded

**Given** all detections have been dismissed
**When** I click "Redact"
**Then** the button is disabled or the system informs me there is nothing to redact

**Given** an invalid or expired session ID
**When** `POST /api/redact/{session_id}` is called
**Then** it returns HTTP 404 with `{"error": "Session not found"}`

### Story 5.2: True PDF Redaction via PyMuPDF

As a user,
I want PII text permanently removed from the PDF data layer with black bars in the visual layer,
So that redacted content is irrecoverable by any tool — not just hidden behind cosmetic rectangles.

**Acceptance Criteria:**

**Given** a list of non-dismissed `Detection` objects and the source PDF
**When** `redactor.redact(detections, pdf_path)` is called
**Then** it adds redaction annotations at each detection's `bbox` coordinates and calls `page.apply_redactions()` to permanently remove the underlying text (FR18, FR19)

**Given** a redacted PDF
**When** I run `pdftotext redacted.pdf -`
**Then** zero PII strings from the original detections appear in the output (NFR9)

**Given** a redacted PDF
**When** I run `page.get_text()` via PyMuPDF on each page
**Then** zero PII strings from the original detections appear (NFR9)

**Given** the redaction process
**When** I inspect the output visually
**Then** black bars appear where PII was located, and the rest of the document is intact (FR19)

### Story 5.3: PDF Sanitization Pipeline

As a user,
I want the redacted PDF fully sanitized — metadata stripped, history purged, orphaned objects removed,
So that no PII leaks through metadata, document history, or unreferenced objects.

**Acceptance Criteria:**

**Given** a redacted PDF
**When** the sanitization pipeline runs
**Then** `doc.set_metadata({})` strips the Info dictionary (Author, Title, Subject, Creator, Producer) (FR20)

**Given** a redacted PDF
**When** the sanitization pipeline runs
**Then** `doc.del_xml_metadata()` removes XMP metadata (FR21)

**Given** a redacted PDF
**When** the sanitization pipeline runs
**Then** `doc.save(garbage=4, deflate=True, clean=True)` removes orphaned objects and writes a non-incremental file (FR22, FR23)

**Given** the sanitized output
**When** I inspect `doc.metadata` via PyMuPDF
**Then** all fields are empty strings or None

**Given** the sanitized output
**When** I call `doc.get_xml_metadata()`
**Then** it returns empty or None

**Given** a 10-page PDF
**When** the full redaction + sanitization pipeline runs
**Then** it completes in under 5 seconds (NFR5)

### Story 5.4: Redacted PDF Download & Cleanup

As a user,
I want to download the redacted PDF as a new file with `_redacted` suffix, with my original untouched,
So that I have both versions and can verify the result.

**Acceptance Criteria:**

**Given** redaction and sanitization complete
**When** the API responds to `POST /api/redact/{session_id}`
**Then** it returns the redacted PDF as a file download with filename `{original_name}_redacted.pdf` (FR24)

**Given** the redacted PDF is returned
**When** I check the original file
**Then** it is completely untouched — identical to what was uploaded (FR24)

**Given** the download completes
**When** the backend finalizes the session
**Then** all temp files for that session are deleted via `TempFileManager` (FR26, NFR8)

**Given** the frontend receives the download
**When** the file is saved
**Then** the frontend transitions to `complete` state with a success message and option to process another document (back to `idle`)

**Given** the `complete` state
**When** I inspect the frontend
**Then** it shows the filename of the redacted PDF and a "Process another document" action

## Epic 6: Evaluation Framework & Verification

Developers and hackathon reviewers can verify detection accuracy via per-entity-type F1 metrics and confirm redaction completeness via automated pdftotext verification on test documents.

### Story 6.1: Evaluation Corpus — Test Documents & Ground Truth

As a developer,
I want a corpus of at least 5 French-language test PDFs with ground-truth PII annotations,
So that detection accuracy can be measured objectively and reproducibly.

**Acceptance Criteria:**

**Given** the `tests/evaluation/corpus/` directory
**When** I list its contents
**Then** it contains at least 5 PDF files with corresponding ground-truth JSON files (e.g., `doc_01.pdf` + `doc_01_ground_truth.json`) (FR40)

**Given** a ground-truth JSON file
**When** I inspect its structure
**Then** each entry has `text`, `entity_type` (person/address/phone/email), `page`, `start`, `end` — matching the `Detection` model fields

**Given** the test documents
**When** I inspect their content
**Then** they contain realistic French administrative/medical text with a mix of all 4 entity types across headers, body, footers, and tables

**Given** the corpus
**When** I inspect for PII
**Then** all names, addresses, phone numbers, and email addresses are synthetic (not real people)

### Story 6.2: F1 Evaluation Framework

As a developer,
I want an evaluation script that measures precision, recall, and F1 per entity type,
So that I can track detection accuracy and demonstrate it to hackathon judges.

**Acceptance Criteria:**

**Given** a test document and its ground-truth annotations
**When** `evaluate.py` runs the detection pipeline on the document
**Then** it compares predicted detections against ground truth using exact text match per entity type

**Given** the comparison results
**When** metrics are computed
**Then** it reports precision, recall, and F1 for each entity type (person, address, phone, email) separately (FR38)

**Given** the full corpus
**When** `make eval` (or `pytest -m eval`) is run
**Then** it processes all test documents and prints a summary table with per-entity-type and overall metrics

**Given** the evaluation results
**When** I inspect the output format
**Then** it displays a clear table suitable for the demo video and technical write-up

### Story 6.3: Automated Redaction Verification

As a developer,
I want automated tests that prove redacted PDFs contain zero extractable PII,
So that true redaction can be verified in CI and demonstrated to reviewers.

**Acceptance Criteria:**

**Given** a test document processed through the full pipeline (detect → redact)
**When** `pdftotext redacted_output.pdf -` is run
**Then** zero PII strings from the ground truth appear in the extracted text (FR39, NFR9)

**Given** a redacted test document
**When** `doc.metadata` is inspected via PyMuPDF
**Then** all metadata fields are empty

**Given** a redacted test document
**When** `doc.get_xml_metadata()` is called
**Then** it returns empty or None

**Given** a redacted test document
**When** the raw file bytes are searched for ground-truth PII strings
**Then** zero matches are found

**Given** these verification tests
**When** `pytest -m leakage` is run
**Then** all PII leakage tests pass across the full evaluation corpus
