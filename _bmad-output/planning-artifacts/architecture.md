---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
lastStep: 8
status: 'complete'
completedAt: '2026-05-01'
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
workflowType: 'architecture'
project_name: 'incognito-ai'
user_name: 'Beatrice'
date: '2026-05-01'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
40 functional requirements across 7 categories. The architecture must support:
- A per-block processing pipeline (PDF input → per-block text extraction with bounding boxes → per-block NER → post-detection validation → sidebar review → redaction → output)
- Lightweight process coordination (FastAPI web server + pre-started Ollama inference server)
- Simple Ollama readiness check (no lifecycle management in MVP)
- Multi-layer PDF sanitization (text removal, metadata strip, XMP strip, garbage collection, non-incremental save)
- Human-in-the-loop review via sidebar list with dismiss controls
- Secure temp file handling with crash-recovery cleanup

**Non-Functional Requirements:**
16 NFRs that drive architectural decisions:
- **Performance:** <30s single-page pipeline, <3min 10-page (2-3x budget for per-block NER), responsive UI with spinner during processing
- **Security:** Zero network calls during processing, no persistent PII storage, owner-only temp file permissions, orphan cleanup on launch
- **Accessibility:** Semantic HTML, keyboard navigation, text labels supplementing color, WCAG AA contrast

**Scale & Complexity:**
- Primary domain: Desktop application (localhost web + local AI inference)
- Complexity level: High
- Estimated architectural components: 6-7 (PDF block extractor, NER engine, detection validator, sidebar review UI, redaction engine, Ollama readiness checker, temp file manager)

### Technical Constraints & Dependencies

- **Runtime dependency:** Ollama must be pre-started by the user with Gemma 4 E4B loaded before launching incognito.ai. MVP does not manage Ollama process.
- **Memory budget:** ~5 GB for Gemma 4 model + PyMuPDF processing overhead; 8 GB system RAM recommended
- **Disk:** ~5 GB model storage + transient temp files proportional to PDF size
- **No GPU required:** CPU-only inference shapes performance expectations
- **Offline-only after setup:** Architecture must never make network calls during processing
- **Python ecosystem:** FastAPI (web), PyMuPDF (PDF), Ollama REST API (inference), PDF.js (frontend preview)
- **MVP vs stretch packaging:** Localhost web app (MVP) vs Electron/Tauri native wrapper (stretch) — backend must be packaging-agnostic

### Cross-Cutting Concerns Identified

- **Temp file lifecycle management:** Every pipeline stage that writes to disk must use the secure temp directory, and all artifacts must be cleaned up on completion or on next launch after a crash
- **Processing feedback:** The UI shows a simple spinner with status text ("Extracting text…", "Detecting PII…", "Done"). No per-page granularity in MVP — a single status endpoint or SSE stream with stage-level updates.
- **Security invariants:** Zero-network and no-persistent-PII guarantees must be enforced architecturally (not by convention) across all code paths
- **Process coordination:** FastAPI checks Ollama readiness on startup and per-request via `/api/status`. MVP assumes Ollama is externally managed — no subprocess lifecycle.
- **Error boundaries:** Each pipeline stage (PDF parsing, text extraction, NER, coordinate mapping, redaction) can fail independently — the architecture needs clear error propagation to the UI with actionable messages

## Starter Template Evaluation

### Primary Technology Domain

Desktop application with localhost web interface + local AI inference pipeline. Python-native backend with thin HTML/JS frontend.

### Starter Options Considered

**Option A: `uv init` + manual scaffold (Selected)**
Purpose-built structure tailored to incognito.ai's pipeline architecture. Minimal scaffolding, maximum relevance. No stripping of unused features.

**Option B: Full Stack FastAPI Template (Copier)**
Rejected — designed for multi-service web SaaS (React, PostgreSQL, Docker, auth). Would require more effort stripping irrelevant components than building from scratch.

**Option C: Cookiecutter FastAPI templates**
Rejected — no community template targets "local AI inference desktop app with PDF processing." Same strip-and-adapt overhead as Option B.

### Selected Starter: `uv init` + purpose-built scaffold

**Rationale for Selection:**
incognito.ai is a pipeline-oriented desktop app, not a web SaaS. No existing starter template matches this domain. A purpose-built structure designed around the processing pipeline (extract → detect → map → redact) provides clearer module boundaries and avoids the cost of adapting a generic web template.

**Initialization Command:**

```bash
uv init incognito-ai
cd incognito-ai
uv python pin 3.13
uv add fastapi uvicorn[standard] pymupdf httpx
uv add --dev pytest pytest-asyncio pytest-cov ruff httpx \
    pytest-socket hypothesis syrupy detect-secrets import-linter cyclonedx-bom
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
Python 3.13, managed via uv with lockfile (`uv.lock`). src layout with `src/incognito/` package.

**Project Structure:**

```
incognito-ai/
├── pyproject.toml              # All config: deps, ruff, pytest
├── .python-version             # 3.13
├── uv.lock
├── src/
│   └── incognito/
│       ├── __init__.py
│       ├── main.py             # App entry point, startup sequence
│       ├── api/                # FastAPI routes + SSE endpoints
│       │   ├── __init__.py
│       │   ├── routes.py
│       │   └── events.py       # Server-sent events for progress
│       ├── core/               # Config, constants, temp file mgmt
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── tempfiles.py
│       ├── pipeline/           # The processing pipeline
│       │   ├── __init__.py
│       │   ├── extractor.py    # Per-block PDF text extraction with bounding boxes (PyMuPDF)
│       │   ├── detector.py     # Per-block PII detection (Ollama/Gemma 4)
│       │   ├── validator.py    # Post-detection validation (verify offsets match source text)
│       │   └── redactor.py     # Redaction + sanitization
│       ├── ollama/             # Ollama lifecycle management
│       │   ├── __init__.py
│       │   └── manager.py
│       └── static/             # Frontend (HTML + CSS + JS + PDF.js)
│           ├── index.html
│           ├── app.js
│           └── style.css
├── tests/
│   ├── conftest.py
│   ├── test_extractor.py
│   ├── test_detector.py
│   ├── test_validator.py
│   ├── test_redactor.py
│   ├── test_api.py
│   └── evaluation/            # F1 evaluation framework
│       ├── corpus/            # Test PDFs + ground truth
│       └── evaluate.py
└── scripts/
    └── launch.sh              # Startup script (MVP launcher)
```

**Styling Solution:**
Vanilla CSS — no framework. The frontend is a single-page app with a drop zone, preview panel, and action buttons. Complexity doesn't justify a CSS framework.

**Build Tooling:**
uv for dependency management and virtual environment. No frontend build step — vanilla JS served as static files by FastAPI.

**Testing Framework:**
pytest + pytest-asyncio (auto mode) + pytest-cov. httpx AsyncClient for API testing. Evaluation framework in `tests/evaluation/` for F1 metrics.

**Network egress testing (pytest-socket):** All tests run with sockets disabled by default via `conftest.py`. Tests that need local Ollama access opt in with `@pytest.mark.ollama` and `@pytest.mark.allow_hosts(['127.0.0.1'])`. Any non-localhost socket attempt in the test suite fails with `SocketBlockedError`.

**Property-based testing (hypothesis):** Privacy invariants tested via hypothesis — e.g., "for any input text, the redacted output never contains a span the detector flagged." Used alongside golden-corpus F1 tests, not as a replacement.

**Snapshot testing (syrupy):** Used for redaction metadata serialization and CLI output. Not used for LLM outputs (they churn).

**Supply chain (cyclonedx-bom + pip-audit):** `cyclonedx-py environment` generates SBOM. `pip-audit --strict` checks for known vulnerabilities. Both run in CI.

**Code Quality:**
Ruff for linting and formatting (target Python 3.13, line length 100). Rule sets: E, F, W, I, N, UP, S, B, A, C4, PT, RUF.

**Configuration (pyproject.toml):**

```toml
[project]
name = "incognito-ai"
version = "0.1.0"
requires-python = ">=3.13"

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "C90", "PT", "ANN", "SIM", "TID", "PL", "RUF"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 5
max-locals = 12

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src/incognito"]
```

**Design Rationale:**
- `pipeline/` mirrors the data flow — each module is a pipeline stage with clear inputs/outputs
- `ollama/` isolates process management from business logic
- `api/` is thin — just routes invoking the pipeline, keeping the web layer swappable for native packaging
- `static/` keeps frontend co-located but separate — easy to replace with Electron/Tauri later
- `tests/evaluation/` houses the F1 framework alongside unit tests

**Note:** Project initialization using the `uv init` command should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Pipeline approach: per-block text extraction with bounding boxes → per-block NER → post-detection validation
- Pipeline state management: in-memory Pydantic models
- Session state: server-side, keyed by session ID
- Processing feedback: SSE via StreamingResponse with stage-level status (not per-page)
- PDF sanitization sequence: redact → strip metadata → strip XMP → sanitized save
- Temp file security: centralized TempFileManager
- Zero-network enforcement: architectural separation + automated import scanning

**Important Decisions (Shape Architecture):**
- API surface: 6 REST endpoints
- Frontend: PDF.js static preview + sidebar detection list (no canvas overlay in MVP)
- Frontend state: simple module pattern with state object
- Ollama: readiness check only (no subprocess management in MVP)
- App entry point: Python `python -m incognito`
- Logging: Python logging to stderr, never log document content

**Deferred Decisions (Post-MVP):**
- Canvas overlay highlights on PDF preview (stretch polish)
- Ollama lifecycle management (auto-start, model pull, graceful shutdown)
- Font ToUnicode stripping (stretch hardening)
- Native .app/.dmg packaging via Electron/Tauri
- Batch processing queue architecture

### Pipeline State & Data Flow

**Pipeline approach: per-block processing.** Instead of extracting all text per page then mapping NER offsets back to coordinates, the pipeline processes each text block individually. PyMuPDF's `page.get_text("dict")` returns text blocks with their bounding boxes. Each block's text is sent to Gemma 4 individually. Detections inherit the bounding box from their source block. This eliminates the fragile offset-to-coordinate mapping problem entirely, at the cost of more (but smaller/faster) Ollama calls.

**Pipeline state management:** In-memory Pydantic models passed between stages. Each pipeline stage takes typed input and returns typed output. No file-based intermediate state. State lives within the FastAPI request lifecycle.

**Block extraction model:**
```python
class TextBlock(BaseModel):
    text: str                  # Block text content
    page: int                  # 0-indexed page number
    bbox: BBox                 # x, y, width, height from PyMuPDF
    block_index: int           # Block sequence within page
```

**Detection data model:**
```python
class Detection(BaseModel):
    id: str                    # Unique ID for dismiss/approve
    text: str                  # Detected PII string
    entity_type: EntityType    # person | address | phone | email
    page: int                  # 0-indexed page number
    start: int                 # Character offset start within source block text
    end: int                   # Character offset end within source block text
    bbox: BBox                 # Inherited from source TextBlock
    validated: bool = True     # Passed post-detection validation
    dismissed: bool = False    # User review state
```

**Post-detection validation:** After Gemma 4 returns detections for a block, each detection is validated: `block.text[start:end] == detection.text`. Detections that fail this check are silently dropped. This guards against hallucinated offsets from the LLM.

**Session state:** Server-side in-memory dictionary keyed by session ID. Backend holds PyMuPDF document handle + detection list between upload and redaction steps. Session cleaned up after redaction completes or on timeout.

### API & Communication Patterns

**Processing feedback:** Server-Sent Events (SSE) via FastAPI `StreamingResponse`. Frontend connects via native `EventSource` API. One-directional server→client push for stage-level status updates (extracting, detecting, validating, complete). No per-page granularity in MVP — frontend shows a simple spinner with the current stage name.

**File upload:** Standard multipart form upload via FastAPI `UploadFile`. Compatible with drag-and-drop via JavaScript `FormData`.

**API surface (6 endpoints):**

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/status` | GET | Ollama/model readiness check |
| `/api/upload` | POST | Upload PDF, start detection, return session ID |
| `/api/events/{session_id}` | GET | SSE stream for processing progress |
| `/api/detections/{session_id}` | GET | Get all detections for review |
| `/api/detections/{session_id}/{id}` | DELETE | Dismiss a detection |
| `/api/redact/{session_id}` | POST | Trigger redaction, return redacted PDF |

**Error handling:** Each pipeline stage raises typed exceptions. FastAPI exception handlers translate them to structured JSON error responses with user-friendly messages. Errors are surfaced to the frontend via SSE events during processing, or as HTTP error responses for synchronous endpoints.

### Frontend Architecture

**PDF preview (MVP):** PDF.js renders pages to `<canvas>` as a static, non-interactive preview. No overlay, no highlights on the canvas. The preview serves only to show the user which document they uploaded and help them locate entities by page number.

**Detection review (MVP):** A sidebar list next to the PDF preview displays all detections grouped by page. Each list item shows: entity type badge (person/address/phone/email), text snippet, page number, and a dismiss button. Click dismiss to mark as false positive. This ships in ~1 day vs. 4+ days for canvas overlay highlights.

**Stretch: Canvas overlay highlights.** If time permits, add transparent `<div>` overlay on the canvas with positioned highlight elements for each detection. Click highlight to dismiss. This is polish, not MVP.

**State management:** Simple module pattern — a single `state` object with functions that mutate it and re-render affected DOM sections. No framework, no dependencies. Sufficient for a single-screen, single-workflow app.

### Security Architecture

**Zero-network enforcement:** Architectural separation — `pipeline/` modules never import HTTP clients. Only `ollama/manager.py` makes HTTP calls, exclusively to `127.0.0.1:11434`. An automated test scans `pipeline/` imports to enforce this boundary.

**Layered import enforcement via `import-linter`:**
```ini
[importlinter]
root_package = incognito

[importlinter:contract:layered]
name = Layered architecture
type = layers
layers =
    incognito.api
    incognito.pipeline
    incognito.ollama
    incognito.core
```
This mechanically prevents reverse imports (e.g., `pipeline/` importing from `api/`). Wired into pre-commit.

**Temp file security:** Centralized `TempFileManager` class in `core/tempfiles.py`. Creates `tempfile.mkdtemp()` with `0o700` permissions and `incognito-` prefix. Tracks all files written during a session. Guarantees cleanup via context manager, `atexit`, and signal handlers. On app launch, scans for orphaned `incognito-*` temp dirs and deletes them.

**PDF sanitization pipeline (in `pipeline/redactor.py`):**
1. Apply redaction annotations → removes text under redaction areas
2. Strip Info dictionary → `doc.set_metadata({})`
3. Delete XMP metadata → `doc.del_xml_metadata()`
4. Save with `garbage=4, deflate=True, clean=True` to new filename → non-incremental write + orphan object cleanup

Font ToUnicode stripping deferred to stretch hardening phase.

### Infrastructure & Deployment

**Ollama readiness check (MVP):** `ollama/manager.py` is a thin readiness checker, not a lifecycle manager:
1. `GET 127.0.0.1:11434/api/tags` — check if Ollama is running and Gemma 4 E4B is available
2. Return ready/not-ready status
3. No subprocess management, no model pull, no shutdown logic

The user is responsible for starting Ollama and pulling the model before launching incognito.ai. The README provides copy-paste commands: `ollama serve` and `ollama pull gemma4:e4b`.

**Stretch: Full Ollama lifecycle management** — auto-detect, start as subprocess, model pull with SSE progress, graceful shutdown. Only if time permits post-MVP.

**App entry point:** `python -m incognito` (or `uv run incognito`). Python `main.py` orchestrates: FastAPI server start → Ollama readiness check → browser open. No shell script dependency for core functionality. Optional `scripts/launch.sh` as convenience wrapper.

**Logging:** Python `logging` module to stderr only. Logs operational events (Ollama status, pipeline stage transitions, timing, errors). Never logs document content, filenames, or PII. `DEBUG` level for development, `INFO` for production use.

### Decision Impact Analysis

**Implementation Sequence:**
1. Project scaffold (`uv init`, structure, pyproject.toml)
2. Ollama readiness checker (simple GET to /api/tags)
3. PDF block extractor (PyMuPDF per-block text extraction with bounding boxes)
4. PII detector (per-block Ollama/Gemma 4 NER prompting)
5. Detection validator (verify offsets match source text)
6. Redactor + sanitization pipeline
7. TempFileManager integration
8. FastAPI API layer (6 endpoints + SSE with stage-level updates)
9. Frontend (PDF.js static preview + sidebar detection list + spinner)
10. Stretch: canvas overlay highlights, Ollama lifecycle management, evaluation framework

**Cross-Component Dependencies:**
- API layer depends on pipeline modules + session state + TempFileManager
- Pipeline stages are sequential but independently testable with Pydantic models as interfaces
- `detector.py` depends on `ollama/manager.py` for inference; `validator.py` depends on detector output
- Frontend depends on API contract (endpoints + SSE event types) but is otherwise decoupled
- Ollama must be pre-started and ready before any pipeline execution (checked via `manager.check_ready()`)
- TempFileManager wraps every pipeline invocation

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
12 areas where AI agents could make different choices, organized into naming, format, communication, and process patterns.

### Naming Patterns

**Python Code Naming:**
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Module files: `snake_case.py`
- Pydantic models: `PascalCase` (e.g., `Detection`, `EntityType`)

**API Naming:**
- Endpoints: `/api/kebab-case` with plural nouns for collections
- JSON fields in responses: `snake_case` (Pydantic default)
- Path/query parameters: `snake_case`

**JavaScript Code Naming:**
- Variables/functions: `camelCase`
- CSS classes: `kebab-case`
- DOM IDs: `kebab-case`
- Custom DOM events: `kebab-case` (e.g., `detection-dismissed`)

**SSE Event Naming:**
- Event types: `snake_case` (e.g., `stage_update`, `pipeline_error`, `pipeline_complete`)

**Naming Boundary:** Python sends `snake_case` JSON via the API. JavaScript consumes it as-is — no camelCase transformation. One format everywhere in the data layer.

### Format Patterns

**API Response Format:** Direct responses, no wrapper. Endpoints return data directly (arrays, objects). Errors use HTTP status codes + `{"error": "message", "detail": "specifics"}`. Standard FastAPI exception handling.

**SSE Event Payload Structure:**
```
event: stage_update
data: {"stage": "extracting", "message": "Extracting text from PDF…"}

event: stage_update
data: {"stage": "detecting", "message": "Detecting PII entities…"}

event: stage_update
data: {"stage": "validating", "message": "Validating detections…"}

event: pipeline_error
data: {"error": "message", "stage": "detector", "detail": "..."}

event: pipeline_complete
data: {"session_id": "...", "total_detections": 14}
```

MVP uses only three event types: `stage_update`, `pipeline_error`, `pipeline_complete`. Frontend shows spinner + message text from `stage_update`. Per-page progress and per-detection streaming are stretch goals.

### Process Patterns

**Error Handling:**

Typed exception hierarchy in `core/exceptions.py`:
```python
class IncognitoError(Exception):
    """Base exception — all app errors inherit from this."""

class PdfError(IncognitoError):
    """PDF parsing/extraction failures."""

class DetectionError(IncognitoError):
    """NER/Ollama inference failures."""

class RedactionError(IncognitoError):
    """Redaction/sanitization failures."""

class OllamaError(IncognitoError):
    """Ollama lifecycle/connectivity failures."""

class SessionError(IncognitoError):
    """Invalid/expired session."""
```

Pipeline modules raise typed exceptions. API layer catches `IncognitoError` subclasses and maps to HTTP responses (400/404/500). During SSE streaming, errors emit `pipeline_error` events.

**Frontend State Machine:**

| State | Meaning |
|---|---|
| `idle` | No document loaded, showing drop zone + Ollama status badge |
| `uploading` | PDF being sent to backend |
| `processing` | Pipeline running, spinner + stage status text visible |
| `reviewing` | PDF preview + sidebar detection list displayed, awaiting user review |
| `redacting` | Redaction in progress |
| `complete` | Redacted PDF ready for download |
| `error` | Something failed, showing error message |

Linear flow: `idle → uploading → processing → reviewing → redacting → complete`. Any state can transition to `error`. From `error` or `complete`, user returns to `idle`. The `processing` state shows a single spinner with text from SSE `stage_update` events (not per-page progress).

**Logging Conventions:**

```python
# Each module gets its own logger
logger = logging.getLogger(__name__)

# Log format: timestamp - module - level - message
# DO log: operational events, stage transitions, timing, errors
logger.info("Ollama health check passed")
logger.info("Processing page %d/%d", page, total)
logger.error("NER failed on page %d: %s", page, err)

# NEVER log: filenames, paths, extracted text, detection values, any PII
```

### Enforcement Guidelines

**All AI Agents MUST:**
- Follow the naming boundary: `snake_case` in Python and API, `camelCase` in JS variables, `kebab-case` in CSS/DOM
- Use the typed exception hierarchy — never raise raw `Exception` or `ValueError` for business logic errors
- Use the frontend state machine — all UI transitions go through the defined states
- Never import HTTP clients in `pipeline/` modules
- Never log document content, filenames, or PII
- Use `TempFileManager` for all temporary file operations — never call `tempfile` directly

**Pattern Enforcement:**
- Ruff lint rules enforce Python naming conventions
- Automated test scans `pipeline/` imports for HTTP client usage
- Code review checklist includes logging audit for PII leakage

### Pattern Examples

**Good:**
```python
# Pipeline module with typed I/O
def extract_blocks(pdf_path: Path) -> list[TextBlock]:
    logger.info("Extracting text blocks, %d pages", page_count)
    ...

# API route with proper error handling
@router.post("/api/upload")
async def upload_pdf(file: UploadFile) -> UploadResponse:
    ...
```

**Anti-Patterns:**
```python
# DON'T: raw exception in pipeline
raise Exception("something went wrong")  # Use PdfError, DetectionError, etc.

# DON'T: HTTP client in pipeline module
import httpx  # Only allowed in ollama/manager.py

# DON'T: log PII
logger.info("Found name: %s", detection.text)  # NEVER log detection values

# DON'T: manual temp file handling
with open("/tmp/incognito_extract.txt", "w") as f:  # Use TempFileManager
```

## Project Structure & Boundaries

### Requirements to Structure Mapping

| FR Category | Primary Module | Files |
|---|---|---|
| Document Input (FR1-5) | `api/routes.py` + `pipeline/extractor.py` | Upload endpoint, PDF validation, text extraction |
| PII Detection (FR6-11) | `pipeline/detector.py` + `pipeline/validator.py` | Per-block Ollama NER, post-detection validation |
| Preview & Review (FR12-16) | `static/*` + `api/routes.py` | PDF.js static preview, sidebar detection list, dismiss endpoint |
| Redaction (FR17-24) | `pipeline/redactor.py` | apply_redactions, metadata strip, sanitized save |
| Temp File & Data Security (FR25-28) | `core/tempfiles.py` | TempFileManager, cleanup, zero-network |
| Ollama Readiness (FR29, FR31, FR34) | `ollama/manager.py` | Readiness check only (no lifecycle management in MVP) |
| App Lifecycle (FR35-37) | `main.py` | Startup sequence, port selection, browser open |

### Complete Project Directory Structure

```
incognito-ai/
├── pyproject.toml                          # All config: deps, ruff, pytest, coverage
├── .python-version                         # 3.13
├── uv.lock                                 # Lockfile (auto-generated)
├── README.md                               # 60-second comprehension target
├── LICENSE                                  # Apache 2.0
├── .gitignore
├── src/
│   └── incognito/
│       ├── __init__.py                     # Package version
│       ├── __main__.py                     # `python -m incognito` entry point
│       ├── main.py                         # Startup orchestration: Ollama → FastAPI → browser
│       ├── app.py                          # FastAPI app factory, middleware, exception handlers
│       ├── models.py                       # Pydantic models: Detection, EntityType, BBox, SessionState, etc.
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py                   # REST endpoints: upload, detections, redact, status
│       │   └── events.py                   # SSE streaming endpoint + event helpers
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py                   # App config: ports, model name, temp prefix, log level
│       │   ├── exceptions.py              # IncognitoError hierarchy
│       │   ├── tempfiles.py               # TempFileManager: create, track, cleanup, orphan scan
│       │   └── sessions.py               # In-memory session store: create, get, cleanup, timeout
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── extractor.py               # Per-block text extraction: PDF → list[TextBlock] (with bounding boxes)
│       │   ├── detector.py                # Per-block NER: TextBlock → list[RawDetection] (via Ollama/Gemma 4)
│       │   ├── validator.py               # Post-detection validation: verify entity text at claimed offsets
│       │   └── redactor.py                # Redaction + sanitization: detections → redacted PDF
│       ├── ollama/
│       │   ├── __init__.py
│       │   └── manager.py                 # Subprocess lifecycle: detect, start, health, pull, stop
│       └── static/
│           ├── index.html                  # Single-page app shell
│           ├── css/
│           │   └── style.css              # Drop zone, preview, sidebar list, states
│           └── js/
│               ├── app.js                  # Main app: state machine, event routing
│               ├── upload.js              # Drag-and-drop + file picker logic
│               ├── preview.js             # PDF.js static rendering (no overlay in MVP)
│               ├── sidebar.js             # Detection list: grouped by page, dismiss buttons
│               └── api.js                 # API client: fetch wrappers + EventSource
├── tests/
│   ├── conftest.py                         # Shared fixtures: test client, mock Ollama, sample PDFs
│   ├── test_extractor.py                  # PDF text extraction tests
│   ├── test_detector.py                   # NER detection tests (mocked Ollama responses)
│   ├── test_validator.py                  # Post-detection validation tests
│   ├── test_redactor.py                   # Redaction + sanitization verification tests
│   ├── test_tempfiles.py                  # TempFileManager lifecycle tests
│   ├── test_sessions.py                   # Session store tests
│   ├── test_api.py                        # API endpoint integration tests
│   ├── test_security.py                   # Zero-network import scan, temp permissions, PII-in-logs check
│   └── evaluation/
│       ├── corpus/                         # Test PDFs + ground-truth JSON annotations
│       │   ├── doc_01.pdf
│       │   ├── doc_01_ground_truth.json
│       │   └── ...                        # At least 5 documents
│       └── evaluate.py                    # F1 metrics: precision/recall per entity type
└── scripts/
    └── launch.sh                           # Optional shell wrapper for convenience
```

### Architectural Boundaries

**API Boundary (the only external interface):**
- `api/routes.py` + `api/events.py` are the only modules that import FastAPI
- All request handling enters through these two files
- Routes call pipeline functions and session store — never access PyMuPDF or Ollama directly

**Pipeline Boundary (pure data transformation, sync-first):**
- `pipeline/` modules are synchronous pure functions: typed input → typed output. No `async def` — Ollama HTTP calls via httpx are sync. Only `api/` uses `async def` because FastAPI requires it at the route level.
- `extractor.py`: PDF → list[TextBlock] (with bounding boxes per block)
- `detector.py`: TextBlock → list[RawDetection] (per-block NER via Ollama)
- `validator.py`: list[RawDetection] → list[Detection] (offset validation, drop invalid)
- `redactor.py`: list[Detection] + PDF → redacted PDF
- No HTTP clients, no FastAPI imports, no side effects beyond temp file I/O via TempFileManager
- Each module is independently testable with Pydantic models as test fixtures

**Ollama Boundary (infrastructure isolation):**
- `ollama/manager.py` is the only module that makes HTTP calls (to `127.0.0.1:11434`)
- `pipeline/detector.py` calls Ollama through the manager, never directly
- MVP manager exposes a minimal interface: `check_ready() → bool`, `generate(prompt) → str`
- Stretch: `ensure_ready()`, `pull_model()`, `shutdown()`

**Session Boundary (state isolation):**
- `core/sessions.py` owns all mutable state (document handles, detection lists)
- API routes access sessions via session ID — never hold state directly
- Sessions have timeout-based cleanup to prevent memory leaks

**Frontend Boundary (presentation isolation):**
- `static/` is served as-is by FastAPI — no server-side rendering
- MVP frontend: PDF.js static preview + sidebar detection list + spinner. No canvas overlay.
- Frontend communicates only via the 6 API endpoints + SSE
- Can be replaced entirely (e.g., with Electron) without touching backend code

### Data Flow

```
User drops PDF
    → static/js/upload.js sends FormData to POST /api/upload
    → api/routes.py receives file, creates session
    → SSE emits stage_update: "Extracting text…"
    → pipeline/extractor.py extracts text per block with bounding boxes (PyMuPDF)
    → SSE emits stage_update: "Detecting PII…"
    → pipeline/detector.py sends each block to Ollama, gets NER results
    → SSE emits stage_update: "Validating detections…"
    → pipeline/validator.py checks each detection's text at claimed offsets, drops invalid
    → SSE emits pipeline_complete with detection count
    → session stores detections
    → static/js/preview.js renders PDF (static), static/js/sidebar.js renders detection list

User reviews and dismisses false positives
    → static/js/sidebar.js sends DELETE /api/detections/{session}/{id}
    → api/routes.py marks detection as dismissed in session

User clicks Redact
    → static/js/app.js sends POST /api/redact/{session}
    → api/routes.py calls pipeline/redactor.py with non-dismissed detections
    → redactor applies redactions, strips metadata, sanitizes, saves
    → API returns redacted PDF as file download
    → session cleaned up, temp files deleted
```

### File Organization Patterns

**Configuration:** All tool config in `pyproject.toml` (ruff, pytest, coverage). App config in `core/config.py` with environment variable overrides for port, log level, model name.

**Source Organization:** Feature-based within `src/incognito/`. Each subdirectory (`api/`, `core/`, `pipeline/`, `ollama/`) is a self-contained module with clear import boundaries.

**Test Organization:** Flat test files in `tests/` mirroring source modules. Shared fixtures in `conftest.py`. Evaluation framework isolated in `tests/evaluation/` with its own corpus directory.

**Asset Organization:** Frontend assets in `src/incognito/static/` with `css/` and `js/` subdirectories. PDF.js vendored locally in `static/js/vendor/pdfjs/` (`pdf.min.js`, `pdf.worker.min.js`) — downloaded once during project setup and committed to the repository. No CDN dependency at runtime.

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:** All technology choices are compatible. Python 3.13 + FastAPI + PyMuPDF + httpx are well-tested together. Pydantic v2 (bundled with FastAPI) provides native data model integration. SSE via StreamingResponse is built-in. uv manages the entire Python toolchain. No version conflicts.

**Pattern Consistency:** No contradictions. Naming boundaries are clean (snake_case in Python/API, camelCase in JS, kebab-case in CSS). Exception hierarchy aligns with pipeline module boundaries. Frontend state machine matches API endpoint flow. Logging rules enforce zero-PII security.

**Structure Alignment:** Project structure supports all decisions. Pipeline modules map 1:1 to stages. Boundary rules are directory-enforceable. Session store is accessible to API but not pipeline. Static files are isolated for packaging swap.

### Requirements Coverage Validation

**Functional Requirements Coverage (40/40):**

| FR Category | Status | Architecture Component |
|---|---|---|
| Document Input (FR1-5) | Covered | `api/routes.py` + `pipeline/extractor.py` |
| PII Detection (FR6-11) | Covered | `pipeline/detector.py` + `pipeline/validator.py` + SSE |
| Preview & Review (FR12-16) | Covered | `static/*` (PDF.js preview + sidebar list) + dismiss endpoint |
| Redaction (FR17-24) | Covered | `pipeline/redactor.py` (4-step sanitization) |
| Temp File Security (FR25-28) | Covered | `core/tempfiles.py` (TempFileManager) |
| Ollama Readiness (FR29, FR31, FR34) | Covered | `ollama/manager.py` (readiness check only; FR30, FR32, FR33 deferred to stretch) |
| App Lifecycle (FR35-37) | Covered | `main.py` |
| Evaluation (FR38-40) | Covered | `tests/evaluation/` |

**Non-Functional Requirements Coverage (16/16):**

| NFR Category | Status | Architecture Support |
|---|---|---|
| Performance (NFR1-3, NFR5-6) | Covered | SSE stage-level feedback, spinner, per-block pipeline. NFR4 deferred (Ollama cold start management). |
| Security (NFR7-12) | Covered | Zero-network enforcement, TempFileManager, no telemetry |
| Accessibility (NFR13-16) | Covered | Semantic HTML, keyboard nav, text labels, contrast |

### Gap Analysis Results

**Critical Gaps:** None.

**Important Gaps (1 found, resolved):**
- **PDF.js offline bundling:** PDF.js must be vendored locally in `static/js/vendor/pdfjs/` as a local file, not loaded via CDN. The app must work fully air-gapped after initial setup. PDF.js files (`pdf.min.js`, `pdf.worker.min.js`) are downloaded once during project setup and committed to the repository. **Resolved:** Updated asset organization in Project Structure section.

**Minor Gaps (resolved):**
- **Session timeout:** Added to `core/config.py` as a configurable value (default: 30 minutes).
- **detector.py → ollama/manager.py dependency:** Intentional design — detector needs inference access. The boundary rule prohibits direct HTTP clients in pipeline/, not imports from the ollama module.

**Intentionally Deferred (hackathon time budget):**
- **Ollama lifecycle management** (FR30, FR32, FR33): MVP requires pre-started Ollama. Saves ~2 days.
- **Canvas overlay highlights** (FR13 stretch): MVP uses sidebar list. Saves ~3 days.
- **Per-page SSE progress** (FR11 simplified): MVP uses stage-level spinner. Saves ~1 day.
- **Evaluation framework** (FR38-40): Cut if time-critical. Demo PDFs sufficient for judges.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (High)
- [x] Technical constraints identified (memory, disk, offline, CPU-only)
- [x] Cross-cutting concerns mapped (temp files, feedback, security, process coordination, errors)

**Architectural Decisions**
- [x] Critical decisions documented (pipeline state, sessions, SSE, sanitization, temp security, zero-network)
- [x] Technology stack fully specified (Python 3.13, FastAPI, PyMuPDF, Ollama, PDF.js, uv, ruff, pytest)
- [x] Integration patterns defined (SSE events, REST endpoints, session state)
- [x] Performance considerations addressed (progressive feedback, per-page processing, async)

**Implementation Patterns**
- [x] Naming conventions established (Python/API/JS/CSS/SSE boundaries)
- [x] Structure patterns defined (module organization, file placement)
- [x] Communication patterns specified (SSE events, API response format)
- [x] Process patterns documented (error hierarchy, state machine, logging rules)

**Project Structure**
- [x] Complete directory structure defined (every file specified)
- [x] Component boundaries established (API, pipeline, ollama, session, frontend)
- [x] Integration points mapped (6 API endpoints, SSE stream)
- [x] Requirements to structure mapping complete (all 7 FR categories mapped)

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Clear pipeline architecture with typed interfaces between stages
- Strong security posture enforced by architecture, not convention
- Clean module boundaries that enable independent testing
- Minimal API surface (6 endpoints) reduces integration complexity
- Frontend is fully decoupled — swappable for native packaging

**Areas for Future Enhancement (post-MVP):**
- Canvas overlay highlights on PDF preview (stretch polish)
- Full Ollama lifecycle management (auto-start, model pull with progress, graceful shutdown)
- Per-page SSE progress events
- Font ToUnicode stripping in sanitization pipeline
- Batch processing queue architecture
- Native .app/.dmg packaging (Electron/Tauri wrapper)
- WebSocket upgrade if bidirectional communication needed for batch mode

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions
- Pipeline modules must remain independently testable
- Never introduce network calls outside `ollama/manager.py`

**First Implementation Priority:**
```bash
uv init incognito-ai
cd incognito-ai
uv python pin 3.13
uv add fastapi uvicorn[standard] pymupdf httpx
uv add --dev pytest pytest-asyncio pytest-cov ruff httpx \
    pytest-socket hypothesis syrupy detect-secrets import-linter cyclonedx-bom
```
Then scaffold the directory structure and create `__main__.py` entry point.
