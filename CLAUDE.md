# Incognito — CLAUDE.md

100% local PII anonymizer for French admin/medical PDFs.
Gemma 4 E4B via Ollama + PyMuPDF. macOS localhost web app (FastAPI), `.dmg` stretch.
Reviewers: Google engineers / YC judges (Kaggle Gemma 4 Good Hackathon, deadline May 18 2026).
Bar: senior Python, indistinguishable from human.

## Stack
- Python 3.13, uv-managed venv, pyproject.toml is canonical, src layout (`src/incognito/`)
- FastAPI + uvicorn for localhost web server, PDF.js vendored locally for preview
- PyMuPDF (fitz) for PDF data-layer redaction (NOT visual blackout)
- Ollama at http://127.0.0.1:11434, model `gemma4:e4b`, called via httpx through `ollama/manager.py`
- Pydantic v2 for all data models (Detection, TextBlock, BBox, EntityType, SessionState)
- pytest, pytest-asyncio, pytest-cov, ruff, mypy --strict, pip-audit, detect-secrets
- poppler-utils `pdftotext` for redaction verification

## Run-it
- `uv sync` then `pytest` must pass on a clean clone, first try.
- `uv run incognito` starts FastAPI server, checks Ollama, opens browser.
- `python -m incognito` is the canonical entry point.
- `make eval` runs the F1 corpus and prints the table.

## Hard rules (privacy is the product)
- ZERO network egress at runtime except localhost:11434. CI enforces this.
- No PII in logs, exceptions, error messages, or temp file names. Ever.
- All temp files via `TempFileManager` in `core/tempfiles.py` — never call `tempfile` directly.
- `TempFileManager` uses `tempfile.mkdtemp()` with `0o700` permissions and `incognito-` prefix.
- Orphaned `incognito-*` temp dirs scanned and deleted on app launch.
- Ollama config asserts `OLLAMA_HOST=127.0.0.1` at startup.
- Pinned dependencies (uv.lock committed). Gemma model SHA verified before load.
- No HTTP client imports in `pipeline/` modules. Only `ollama/manager.py` makes HTTP calls.

## Python conventions
- Type hints everywhere. mypy --strict passes. No `Any` except at IO boundaries.
- pathlib over os.path. Pydantic v2 at module boundaries; plain dicts inside.
- Pure functions by default. The Ollama call is the ONLY side effect that matters.
- No try/except that swallows exceptions — in a redaction tool, `return []` means "no PII found, ship original." Catastrophic.
- Use the typed exception hierarchy in `core/exceptions.py` — never raise raw `Exception`.
- Constants in `core/config.py`. Never magic strings/numbers in modules.
- `from __future__ import annotations` in every module. Prefer `typing.Final`, `typing.Literal`, `typing.assert_never`.
- `pathlib.Path` everywhere, `dataclass(frozen=True, slots=True)` for value types, `enum.StrEnum` for entity-type tags.
- `Iterator[T]` from generators, not `list[T]` materialisation. `match` for tagged unions, if/elif for simple booleans.

## Architecture (pipeline-oriented, typed interfaces)
- `pipeline/extractor.py`  PDF → list[TextBlock]
- `pipeline/detector.py`   TextBlock → list[RawDetection] (NER via Ollama/Gemma 4)
- `pipeline/validator.py`  list[RawDetection] → list[Detection] (verify offsets)
- `pipeline/redactor.py`   list[Detection] + PDF → redacted PDF
- `ollama/manager.py`      readiness check + inference. Only module touching network.
- `api/routes.py`          6 REST endpoints. Thin adapter over pipeline.
- `api/events.py`          SSE streaming (stage_update, pipeline_error, pipeline_complete).
- `core/config.py` config, `core/sessions.py` session store, `core/tempfiles.py` temp I/O, `core/exceptions.py` error hierarchy.
- `models.py`              all Pydantic models. `static/` vanilla HTML/CSS/JS + PDF.js.
- Imports: static/ → api/ → pipeline/ → ollama/. No reverse imports. ruff enforces.

## Naming conventions
- Python + API JSON: `snake_case`. JS: `camelCase`. CSS/DOM: `kebab-case`. SSE events: `snake_case`.
- No camelCase transformation at API boundary — JS consumes snake_case as-is.

## API surface (6 endpoints)
- `GET /api/status`, `POST /api/upload`, `GET /api/events/{session_id}`
- `GET /api/detections/{session_id}`, `DELETE /api/detections/{session_id}/{id}`, `POST /api/redact/{session_id}`

## Frontend state machine
idle → uploading → processing → reviewing → redacting → complete. Any → error. Error/complete → idle.

## Things Claude tends to get wrong on this project
(append after every correction; this list is the point of CLAUDE.md)
-

## Anti-AI tells (review every diff)
- No useless docstrings, no comments restating code. Names carry meaning; delete the noise.
- No ABCs/Protocols with one implementation. No "helper" called once — inline it.
- No async/await for sync work. No premature class hierarchies. Start with functions.
- No try/except returning empty list on error. No defensive None-checks on typed-non-Optional args.
- No magic numbers/strings inline. No inconsistent style within a file. No multi-paragraph preambles in commits.

## Refactor triggers
- File > 200 lines. Function > 30 lines. Cyclomatic complexity > 10 (ruff C901).
## Quality gate (every PR)
- ruff check + ruff format + mypy --strict + pytest -q + pytest -m eval + pytest -m leakage + pip-audit + pre-commit run --all-files — all clean.

## /compact instructions
When compacting, preserve: open story file path, current module under edit,
last failing test name and traceback, F1 deltas vs baseline. Drop everything else.

## Three rules
1. Simplicity first. Make every change as simple as possible. Delete > add.
2. No laziness. Find root causes. No band-aids. Senior-developer standards.
3. Minimal impact. Touch only what's necessary. Don't introduce bugs while fixing.
