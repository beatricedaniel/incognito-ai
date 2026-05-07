---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - "product-brief (provided inline by user)"
  - "hackathon-page (Kaggle competition page, pasted by user)"
workflowType: 'prd'
documentCounts:
  briefs: 1
  research: 1
  brainstorming: 0
  projectDocs: 0
classification:
  projectType: desktop_app
  domain: govtech
  complexity: high
  projectContext: greenfield
---

# Product Requirements Document — incognito.ai

**Author:** Beatrice
**Date:** 2026-04-19

## Executive Summary

Organizations handling documents containing personally identifiable information (PII) face a compounding problem: operational knowledge stays siloed because there is no practical way to strip personal data before sharing, and AI adoption is blocked because feeding PII-laden documents into AI systems creates unacceptable privacy and compliance risk. Manual redaction takes 30–60 minutes per document and doesn't scale. Cloud-based anonymization requires sending sensitive data to third parties, defeating the purpose. Existing NLP tools lack accuracy on non-English administrative text and require technical expertise to operate.

incognito.ai is a native macOS desktop application that performs AI-powered true redaction of PII in PDF documents. The user drags a PDF into the app; Gemma 4 E4B, running locally via Ollama, automatically detects person names, addresses, phone numbers, and email addresses; the user reviews color-coded highlights on a PDF preview; and incognito.ai produces a new PDF with all confirmed PII permanently removed from the document's data layer — not hidden behind cosmetic rectangles, but irrecoverably deleted.

The target users are public-sector agents (ministry staff, procurement officers, contract managers, social workers, health administration officers) and professionals in regulated industries (healthcare, legal, finance, insurance) who need to share documents or feed them into AI tools without exposing personal data. Secondary audience: data protection officers seeking GDPR/RGPD-compliant document workflows.

incognito.ai is built for the Kaggle Gemma 4 Good Hackathon (deadline: May 18, 2026), targeting the Safety & Trust impact track. The project is scoped as an MVP by a solo developer working part-time over 30 days.

### What Makes This Special

**True redaction, not cosmetic overlay.** Most PDF annotation tools draw black rectangles over text without removing it — the PII remains extractable by any tool, including AI services. incognito.ai permanently deletes PII from the PDF data layer. A text extraction command on the redacted file returns nothing. This is provable in a live demo and represents a genuine safety innovation.

**The hesitation insight.** Every professional who handles sensitive documents knows the moment: the cursor hovers over "Send" and you wonder whether there's personal data buried in those pages. incognito.ai replaces that doubt with a single action — drag, review, redact — in less time than it takes to hesitate. It doesn't add a step to your workflow; it replaces the step you were already stuck on.

**AI enabler, not just privacy tool.** By producing genuinely clean PDFs, incognito.ai removes the primary blocker to AI adoption in regulated organizations. The redacted document can be safely attached to any AI conversation, uploaded to any cloud service, or fed into any analysis pipeline. incognito.ai secures the AI input pipeline — making it a case of AI for AI safety.

**100% local, zero trust required.** Gemma 4 E4B runs on-device via Ollama. No data leaves the machine. No GPU required (~5 GB RAM). Data sovereignty by architecture, not by policy.

**Human-in-the-loop review.** Every detection is shown before redaction is applied. The user approves or dismisses individual entities. This is non-negotiable in regulated environments where fully automated redaction without human review is not acceptable.

## Project Classification

- **Project Type:** Desktop application (native macOS, `.dmg` installer, drag-and-drop installation)
- **Domain:** Govtech / regulated industries (public administration, healthcare, legal, finance)
- **Complexity:** High (GDPR/RGPD compliance, true PDF redaction security guarantees, AI accuracy directly impacts compliance)
- **Project Context:** Greenfield — new product built from scratch for hackathon submission
- **Platform:** macOS primary, Linux secondary (localhost web interface fallback)
- **Inference Backend:** Ollama (Gemma 4 E4B, local, no GPU required)

## Success Criteria

### User Success

- **The hesitation replacement:** A user with a PII-containing PDF goes from "I need to redact this" to "here's the clean version" in a single drag-and-drop action followed by a brief review. The emotional shift is from doubt to confidence.
- **Performance that sustains the narrative:** Single-page PDF processed in under 30 seconds (text extraction + per-block Gemma 4 NER + result display). 10-page document in under 3 minutes. A spinner with status text keeps the user informed — never a frozen screen.
- **Demo-grade speed:** For the video, use a short 1-page document with few text blocks to keep processing under 10 seconds. If CPU inference is too slow for the demo, pre-load a cached result and show the real flow on a separate take.
- **Trust through proof:** The user can verify redaction quality themselves — run `pdftotext` on the output and see nothing. The trust model is "don't trust me, verify me."

### Business Success (Hackathon Context)

- **Submission accepted** on Kaggle before May 18, 2026, with all required artifacts (video, code, write-up, demo)
- **Compelling narrative:** The demo video clearly communicates the "AI for AI safety" thesis — incognito.ai secures the AI input pipeline by using AI to permanently strip PII before documents enter any AI system
- **Technical credibility:** Code repository and write-up demonstrate genuine, functional implementation — not a prototype, not faked for demo
- **Scoping principle:** Prioritize polish and completeness over feature breadth. A flawlessly executed MVP beats a feature-rich prototype with rough edges. Video, write-up, and README quality matter as much as code — allocate time accordingly.

### Technical Success

- **NER accuracy:** F1 >85% on person names and addresses, >80% on phone numbers and email addresses, measured on synthetic French-language test documents
- **True redaction verification (demo):** `pdftotext redacted_incognito.pdf -` returns zero PII strings. Side-by-side with cosmetic redaction where PII is fully extractable. Uses `pdftotext` from poppler-utils for visual clarity in video.
- **True redaction verification (automated):** PyMuPDF `page.get_text()` on redacted output, searched against ground-truth PII annotations, asserts zero matches. Pass/fail test in CI pipeline.
- **Installation:** App installs via `.dmg` drag-and-drop and launches without terminal on a clean macOS environment (stretch). Minimum: localhost web app launches with a single command.
- **Evaluation corpus:** At least 5 test documents with ground-truth annotations and per-entity-type precision/recall/F1 metrics.

### Measurable Outcomes

| Metric | Target | Verification method |
|---|---|---|
| Single-page processing time | <30 seconds | Timed in demo |
| 10-page processing time | <3 minutes | Timed in evaluation |
| Person name F1 | >85% | Evaluation framework |
| Address F1 | >85% | Evaluation framework |
| Phone number F1 | >80% | Evaluation framework |
| Email F1 | >80% | Evaluation framework |
| PII strings in redacted PDF | 0 | `pdftotext` + PyMuPDF extraction |
| Demo video length | ≤3 minutes | Video edit |
| Writeup length | ≤1,500 words | Word count |
| README comprehension time | <60 seconds | Peer review |
| Kaggle submission | Accepted before May 18 | Kaggle platform |

## User Journeys

### Journey 1: Claire — The Procurement Officer (Happy Path)

Claire is a procurement officer at a regional health agency in Lyon. She manages vendor contracts for medical equipment suppliers across 12 hospitals. Her desk is buried in contract amendment files — each one containing vendor contact names, direct phone numbers, personal email addresses, and office addresses.

Today, her director asks her to share the last quarter's contract negotiation summaries with a sister agency in Marseille that's starting a similar procurement cycle. The documents would save the Marseille team weeks of research — but every file contains vendor representatives' personal data. Under RGPD, she can't just email them.

Claire has done this before: she spent an entire afternoon manually reading through a 15-page contract summary, highlighting names and phone numbers with a black marker in a PDF editor, only to realize later she'd missed an email address buried in a footer. She won't do that again.

She opens incognito.ai from her Applications folder. Drags the contract summary PDF into the window. Within seconds, the document appears with colored highlights: vendor names in red, their office addresses in blue, phone numbers in green, email addresses in amber. She scans the preview — Gemma 4 caught the footer email she missed last time. She spots one false positive: the agency's own public office name highlighted as a person name. She dismisses it with a click. Everything else looks right.

She clicks "Redact." A new PDF appears in her Downloads folder. She opens it — black bars where the PII was, the rest of the document perfectly intact. She drags it into her email to the Marseille team. The cursor doesn't hesitate over "Send." She clicks it immediately.

**Capabilities revealed:** PDF drag-and-drop input, automatic PII detection (4 entity types), color-coded preview by entity type, dismiss false positives, true redaction output, new file in Downloads.

### Journey 2: Claire — First Launch (Setup & Onboarding)

Same Claire, one week earlier. Her colleague mentioned incognito.ai after struggling with manual redaction. Claire downloads the `.dmg` from the project website. She drags the app icon into Applications — the same gesture she uses for any Mac app.

She follows the README: installs Ollama, runs `ollama pull gemma4:e4b` (one-time ~5 GB download), then launches incognito.ai with `uv run incognito`. Her browser opens to a clean screen: a large drop zone ("Drop a PDF here"), a green "AI Ready — 100% local" badge, and nothing else. No menus to learn, no configuration, no account creation. Claire drags a test document — an old contract she's already manually redacted — to see if the tool catches what she caught. It does. She's convinced.

**Capabilities revealed:** Simple setup via README instructions, Ollama readiness check, zero-configuration app start, drop zone UI. Stretch: `.dmg` installation with embedded Ollama and first-launch setup assistant.

### Journey 3: Marc — The Batch Deadline (Multiple Documents)

Marc works in a ministry's labour inspection division. A parliamentary committee has requested anonymized copies of 25 inspection reports for a policy review. The deadline is tomorrow. Each report contains inspector names, company contact persons, employee names mentioned in complaints, site addresses, and phone numbers.

Marc opens incognito.ai and drags all 25 PDFs into the window at once. The app shows a queue: "25 documents — processing 1 of 25." Each document goes through detection, and Marc sees a summary: "Document 1: 14 entities detected (7 names, 3 addresses, 2 phones, 2 emails)." He can review each document's detections or trust the defaults and batch-redact all.

He reviews the first three documents carefully — the detections are accurate. For the remaining 22, he clicks "Redact All" to process them without individual review. An hour later, 25 redacted PDFs sit in his output folder. He spots-checks two at random with `pdftotext` — clean. He sends the package to the committee liaison.

**Capabilities revealed:** Multi-file drag-and-drop, processing queue with progress, per-document entity summary, batch redact option (trust defaults), output folder organization.

### Journey 4: Nadia — The Skeptical DPO (Verification)

Nadia is the data protection officer at a regional hospital group. A department head wants to use incognito.ai to anonymize patient discharge summaries before feeding them into an AI tool for clinical pattern analysis. Nadia's job is to verify that the tool actually works before she signs off on the workflow.

She creates a test document: a fake discharge summary with known PII — a patient name, doctor name, home address, phone number, and email — placed in headers, body text, footers, and a table cell. She knows exactly what's in the document and where.

She processes it through incognito.ai. The preview shows all her planted PII highlighted. Good. She clicks "Redact" and gets the output PDF. Now the real test.

She opens a terminal: `pdftotext redacted_output.pdf - | grep -i "dupont"` — nothing. She tries the address, the phone number, the email. Nothing. She opens the PDF in a hex editor and searches for the raw strings. Gone. She opens it in Adobe Acrobat and tries "Find" — no results.

She writes her assessment: "The tool performs genuine PDF redaction. PII is removed from the text layer, not merely obscured. The redacted PDF is safe for external sharing and AI ingestion. Approved for use with the following conditions: (1) users must review detections before redacting, (2) the department maintains a log of which documents were processed."

**Capabilities revealed:** True redaction that survives text extraction, hex editor inspection, and PDF search. Verification workflow for compliance sign-off.

### Journey Requirements Summary

| Capability | Journey 1 (Happy Path) | Journey 2 (Setup) | Journey 3 (Batch) | Journey 4 (Verification) |
|---|---|---|---|---|
| PDF drag-and-drop input | ✓ | ✓ | ✓ | ✓ |
| Ollama readiness check + status badge | | ✓ | | |
| Automatic PII detection (4 types) | ✓ | ✓ | ✓ | ✓ |
| Sidebar detection list (page-grouped) | ✓ | ✓ | ✓ | ✓ |
| Dismiss individual detections from sidebar | ✓ | | | |
| True PDF redaction | ✓ | | ✓ | ✓ |
| Redacted file output (original untouched) | ✓ | | ✓ | ✓ |
| Multi-file input + queue | | | ✓ | |
| Per-document entity summary | | | ✓ | |
| Batch redact (skip individual review) | | | ✓ | |
| Processing feedback (spinner + status) | ✓ | | ✓ | |
| Verification via `pdftotext` | | | ✓ | ✓ |

Note: Journey 3 (batch) capabilities are scoped as Phase 2/post-MVP. The MVP fully serves Journeys 1, 2, and 4.

## Domain-Specific Requirements

### Compliance & Regulatory (GDPR/RGPD)

- **Tool purpose is RGPD compliance** — incognito.ai exists to enable lawful document sharing by stripping PII. The tool itself must handle PII responsibly during processing.
- **Temp file security:** Processing writes intermediate files to disk (extracted text, detection results). These must be written to a secure temporary directory and deleted immediately after the redacted PDF is produced. On crash or unexpected termination, a cleanup routine on next launch scans for and deletes orphaned temp files.
- **No telemetry, no logging of document content.** Zero network calls. No analytics. The only persistent artifact is the redacted output PDF.
- **AI limitation disclaimer:** The UI displays a clear notice: "AI detection may miss some entities. Review all detections carefully before redacting." This positions the tool as an aid, not a guarantee — essential for regulated environments.

### Redaction Security (PDF Sanitization Pipeline)

True redaction requires more than `apply_redactions()`. The redacted PDF must be sanitized across multiple layers to eliminate all PII traces:

| Threat | Mitigation | Tool |
|---|---|---|
| PII in text layer | `apply_redactions()` removes text under redaction annotations | PyMuPDF |
| PDF metadata (Author, Title, Subject, Creator) | Strip Info dictionary | PyMuPDF `set_metadata({})` |
| XMP metadata | Strip XML metadata stream | PyMuPDF `del_xml_metadata()` |
| Incremental save history (prior document versions in file) | Full structural rewrite | PyMuPDF `save(garbage=4, deflate=True, clean=True)` on new filename (non-incremental) |
| Orphaned/unreferenced objects | Garbage collection pass | PyMuPDF `save(garbage=4)` |
| Document ID fingerprint | Strip trailer ID | pikepdf `del trailer["/ID"]` (if needed) |
| Font ToUnicode character mapping leakage | Strip ToUnicode entries from font objects post-redaction | pikepdf manual font loop (stretch goal) |

**MVP pipeline:** PyMuPDF handles redaction + metadata + XMP + garbage collection + non-incremental save in a single library. This covers the primary threats. Font ToUnicode stripping and pikepdf/qpdf structural rewrite are stretch hardening steps.

**Verification:** The automated test suite verifies all layers — not just `pdftotext` but also metadata extraction (`doc.metadata`), XMP check (`doc.xref_xml_metadata`), and string search in raw file bytes.

### RGPD Compliance Verification (Mechanically Provable)

Each RGPD principle maps to a code-verifiable property and an automated test:

| RGPD Principle | Code-Verifiable Property | Automated Test |
|---|---|---|
| Data minimisation | No PII stored persistently | grep for `pickle`, `shelve`, `sqlite3` in `src/` → must be empty |
| Purpose limitation | No metadata collection / telemetry | grep for `requests.post`, `httpx.post` → only Ollama localhost |
| Storage limitation | All scratch dirs auto-cleaned | `test_no_temp_files_survive` — assert no `incognito-*` dirs remain after processing |
| Lawful basis (local only) | No outbound network | pytest-socket blocks all non-localhost connections; CI sandbox confirms |
| Right to erasure | Output PDF stripped at data layer via PyMuPDF `apply_redactions`, verified with `pdftotext` | `test_pdftotext_yields_no_pii` — text extraction on redacted output returns zero PII strings |

This table belongs in the README under "RGPD compliance" and is the slide the demo video pauses on.

### Technical Constraints

- **Memory:** Gemma 4 E4B via Ollama requires ~5 GB RAM. PDF processing (PyMuPDF) is lightweight. Total system requirement: ~8 GB RAM recommended.
- **Disk:** Model storage ~5 GB (one-time). Temp files during processing: proportional to PDF size (typically <100 MB). Redacted output: same size as input or smaller.
- **No GPU required.** CPU-only inference via Ollama. Performance targets (10s/page) are CPU-based.
- **Offline-only.** No network calls after initial model download. The app functions fully air-gapped after setup.

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. AI for AI Safety (recursive safety model)**
incognito.ai uses an AI model to make other AI systems safe to use. Gemma 4 identifies PII so that documents can be safely fed into any downstream AI tool — cloud-hosted LLMs, summarization pipelines, classification systems. The tool secures the AI input pipeline using AI. This is the core thesis: AI ensuring AI safety — transparency and reliability in document handling through verifiable, permanent redaction.

**2. Multi-layer PDF sanitization in a consumer-grade tool**
True redaction is well-understood in enterprise document management (Adobe Acrobat Pro, specialized legal tools). But the combination of text-layer removal + metadata stripping + XMP cleanup + garbage collection + non-incremental save — packaged in a free, open-source desktop app aimed at non-technical public-sector workers — is novel. Most open-source PDF redaction tools stop at drawing rectangles.

**3. Local-first AI desktop app pattern**
The "download model on first launch, run forever offline" UX for a desktop AI application is an emerging pattern enabled by Gemma 4's efficiency (E4B runs on CPU, ~5 GB RAM). This is distinct from cloud-based AI tools and from developer-oriented local inference setups (which require terminal, Python, manual model management). incognito.ai packages this into a standard macOS app experience.

**4. Hesitation-replacement UX**
The core interaction design insight — that PII anonymization doesn't add a new step but replaces an existing moment of doubt — is a reframing that changes how the tool is perceived. It's not "one more thing to do before sharing"; it's "the thing you were already stuck on, solved."

### Market Context & Competitive Landscape

**Cloud-based PII detection services (not competitors, but the context):**
- Microsoft Presidio — open-source PII detection library, requires Python, no PDF handling, no redaction
- AWS Comprehend PII Detection — cloud API, requires sending data to AWS
- Google Cloud DLP — cloud API, requires sending data to Google
- All three defeat the purpose for privacy-sensitive organizations: the data must leave the machine

**Enterprise redaction tools:**
- Adobe Acrobat Pro — true redaction capability, but manual entity selection (no AI detection), $23/month, proprietary
- Nuance/Kofax — enterprise document processing, heavy integration, enterprise pricing

**Open-source NER + PDF tools (developer-oriented):**
- spaCy + custom scripts — requires Python, manual pipeline assembly, no GUI
- Stanza (Stanford NLP) — research-grade, no production packaging
- None offer an integrated detect-review-redact desktop workflow

**Gap:** No existing tool combines AI-powered PII detection + true PDF redaction + local inference + consumer-grade desktop UX. incognito.ai occupies an empty niche.

### Innovation Validation

| Innovation claim | Validation method |
|---|---|
| True redaction works (PII irrecoverable) | `pdftotext` extraction test + raw byte search + metadata check on redacted output |
| AI detection accuracy sufficient | F1 metrics on 5+ test documents per entity type |
| Local inference is fast enough | Timed benchmarks: <10s single page, <60s 10-page |
| Non-technical users can operate it | Demo video shows full flow without terminal/command line |
| "AI for AI safety" framing resonates | Demo video clearly shows problem→solution→proof chain; write-up articulates recursive safety model |

## Desktop App Specific Requirements

### Project-Type Overview

incognito.ai is a self-contained desktop application that bundles a local AI inference pipeline (Ollama + Gemma 4 E4B) with a PDF processing workflow. It manages its own AI backend, requires no external services after setup, and interacts with the filesystem for input/output only.

### Platform Support

| Platform | Priority | Delivery method | UI approach |
|---|---|---|---|
| macOS | Primary | `.dmg` with drag-to-Applications (stretch); localhost web app with launcher script (MVP) | Native window via Electron/Tauri (stretch); browser-based FastAPI + HTML (MVP) |
| Linux | Secondary | Launcher script | Localhost web interface (same as MVP macOS) |
| Windows | Out of scope | — | — |

**macOS minimum version:** macOS 12 Monterey or later (Apple Silicon + Intel).
**Linux:** Ubuntu 22.04+ / Debian 12+ as reference.

### System Integration

**Ollama lifecycle management (MVP — simplified):** incognito.ai does NOT manage the Ollama process. On launch:
1. Checks if Ollama is running and model is available via `GET 127.0.0.1:11434/api/tags`
2. Displays "Ready" if Ollama + Gemma 4 E4B are available, or "Please start Ollama with Gemma 4 E4B loaded" if not
3. No subprocess management, no model download, no graceful shutdown logic

**Stretch:** Full Ollama lifecycle management (auto-start, model pull with progress, graceful shutdown) can be added post-MVP if time permits.

**Filesystem interaction:**
- **Input:** User selects PDF files via drag-and-drop or file picker
- **Output:** Redacted PDFs saved to the same directory as the input file, with `_redacted` suffix (e.g., `contract.pdf` → `contract_redacted.pdf`). Original untouched.
- **Temp files:** Written to OS temp directory (`tempfile.mkdtemp()`), deleted immediately after processing. Cleanup on next launch for orphaned files.

No other system integrations. MVP is a standalone window.

### Offline Capabilities

Fully offline after first-launch setup:
- **First launch (online required):** Downloads Ollama binary (if not present) + Gemma 4 E4B model weights (~5 GB). Progress bar shown. One-time operation.
- **Every subsequent launch (offline):** Starts Ollama subprocess, loads model, ready to process. Zero network calls. Functions in air-gapped environments.
- **No cloud dependency at any point in the processing pipeline.**

### Implementation Considerations

**Technology stack (MVP):**
- **Backend:** Python, FastAPI (serves localhost web UI + handles processing)
- **PDF processing:** PyMuPDF (text extraction, redaction annotation, apply_redactions, metadata stripping, sanitized save)
- **AI inference:** Ollama (local server) + Gemma 4 E4B model, called via Ollama's REST API on localhost
- **Frontend:** HTML + CSS + JavaScript (served by FastAPI), PDF.js for preview rendering
- **Packaging (stretch):** Electron or Tauri wrapping the localhost web app into a `.app` bundle with embedded Ollama

**Process architecture:**
- FastAPI server runs on `localhost:<port>` (random available port)
- Ollama runs as a managed subprocess on `localhost:11434`
- Pipeline: PDF → PyMuPDF per-block text extraction (with bounding boxes) → per-block Ollama/Gemma 4 NER → post-detection validation → user review via sidebar list → PyMuPDF apply_redactions + sanitization → output PDF

**Startup sequence (MVP):**
1. Start FastAPI server
2. Check Ollama readiness (`GET 127.0.0.1:11434/api/tags`)
3. Open browser to localhost UI
4. Display ready/not-ready status on main screen

## Project Scoping & Phased Development

### MVP Strategy

**Approach:** Problem-solving MVP — the minimum that proves the core value proposition (AI-powered true redaction, locally) works end-to-end and is demo-ready for hackathon judges.

**Guiding principle:** Polish over breadth. A flawless single-PDF flow beats a rough multi-PDF flow. The demo video is the primary judging artifact — every feature must work perfectly on camera.

**Resource reality:** Solo developer, part-time, ~25 days remaining. The scoping question is always: "Does this make the demo better?"

### Phase 1 — MVP

**Core User Journeys Supported:**
- Journey 1 (Claire — happy path): single PDF, detect, review, redact ✓
- Journey 2 (Claire — first launch): setup assistant with visible Ollama management ✓
- Journey 4 (Nadia — verification): `pdftotext` proof that redaction is genuine ✓

**Must-Have Capabilities:**

| Capability | Notes |
|---|---|
| PDF upload (drag-and-drop + file picker) | Single file for MVP |
| Text extraction from PDF | PyMuPDF `page.get_text()` |
| PII detection via Gemma 4 E4B | 4 entity types: person, address, phone, email |
| Sidebar detection list with page-grouped entities | PDF.js static preview + sidebar list (canvas overlay is stretch) |
| Human-in-the-loop review | Dismiss false positives from sidebar list |
| True PDF redaction | PyMuPDF `apply_redactions()` + sanitization pipeline |
| PDF sanitization | Metadata strip, XMP strip, garbage collection, non-incremental save |
| Redacted PDF download | `_redacted` suffix, original untouched |
| Processing feedback | Simple spinner with status text ("Extracting text…", "Detecting PII…", "Done") |
| AI limitation disclaimer in UI | "Review all detections carefully" notice |
| Temp file cleanup | Secure temp directory, delete after processing, cleanup on launch |
| Ollama readiness check | Check Ollama + model status on launch, show "Ready" or "Please start Ollama" message. MVP requires pre-started Ollama. |
| Post-detection validation | Every detection verified: entity text must exist at claimed offsets in source block. Invalid detections silently dropped. |
| Localhost web interface | FastAPI + HTML, opens in default browser |
| Evaluation framework | 5+ test docs, per-entity F1, automated `pdftotext` verification |
| Demo video (≤3 min) | Hesitation → rewind → live demo → pdftotext proof → impact |
| Technical write-up (≤1,500 words) | Architecture, Gemma 4 usage, evaluation, limitations |
| Public GitHub repo (Apache 2.0) | README enables 60-second comprehension |

**Local inference visibility in the demo:** The video skips Ollama setup entirely — it opens with the app already ready. The "100% local" badge on screen reinforces the safety narrative without wasting demo time on infrastructure. The writeup explains the local-only architecture in detail.

### Phase 2 — Growth (only if time permits before May 18)

- Native macOS `.app` / `.dmg` packaging (Electron/Tauri wrapping localhost app)
- Batch processing (multi-file drag-and-drop, processing queue)
- Color-coded entity type highlights in preview (red/blue/green/amber)
- Per-entity approve/dismiss toggle in review UI
- Linux launcher script

### Phase 3 — Vision (document in write-up as future work)

- Fine-tuned Gemma 4 on domain-specific NER datasets
- Windows support
- Scanned PDF support (OCR + image-level redaction)
- Mobile deployment (Gemma 4 E2B tier)
- Multilingual support beyond French
- Domain-specific entity types (national IDs, contract numbers, case refs) via configuration
- Anonymization history / audit dashboard
- DOCX and other file format support
- Integration with document management systems or AI pipelines

### Minimum Submittable Version (Scope Floor)

If time runs critically short, this is the absolute minimum for a competitive submission:

- ✅ Gemma 4 E4B via Ollama detects PII in extracted PDF text
- ✅ True redaction via PyMuPDF produces clean PDF with black bars
- ✅ Localhost web interface (FastAPI + HTML) for upload, preview, download
- ✅ Ollama readiness check (ready / not ready)
- ✅ Demo video showing full flow + pdftotext verification proof
- ✅ Technical write-up + public repo with README
- ✅ At least 5 test documents with evaluation metrics
- ❌ No native .app/.dmg packaging
- ❌ No batch processing
- ❌ No per-entity color coding (single highlight color acceptable)
- ❌ No per-entity approve/dismiss (show all, redact all)

## Functional Requirements

### Document Input

- **FR1:** User can drag-and-drop a PDF file onto the application window to begin processing
- **FR2:** User can select a PDF file via a file picker dialog as an alternative to drag-and-drop
- **FR3:** System extracts text per block (paragraph/line) from each page of an uploaded PDF, preserving the bounding box of each block as returned by PyMuPDF
- **FR4:** System rejects non-PDF files with a clear error message
- **FR5:** System rejects unsupported PDF types (encrypted, scanned/image-only) with a clear error message

### PII Detection

- **FR6:** System detects person names in extracted PDF text using Gemma 4 E4B via Ollama, processing per-block (not whole-page) to preserve bounding box alignment
- **FR7:** System detects physical addresses in extracted PDF text using Gemma 4 E4B via Ollama
- **FR8:** System detects phone numbers in extracted PDF text using Gemma 4 E4B via Ollama
- **FR9:** System detects email addresses in extracted PDF text using Gemma 4 E4B via Ollama
- **FR10:** System inherits bounding box coordinates from the source text block for each detection — no separate offset-to-coordinate mapping step required
- **FR10a:** System validates every detection post-inference: the detected entity text must exist verbatim at the claimed start:end offsets within the source block. Detections that fail validation are silently dropped.
- **FR11:** System provides processing feedback during detection (simple spinner/status text, not per-page granularity)

### Document Preview & Review

- **FR12:** User can view a rendered preview of the uploaded PDF alongside a sidebar list of detected PII entities (grouped by page, showing entity type and text snippet)
- **FR13:** User can distinguish PII entity types in the sidebar list via text labels and optional color badges (person, address, phone, email). Visual highlights overlaid on the PDF canvas are a stretch goal.
- **FR14:** User can dismiss a false-positive detection from the sidebar list (removes it before redaction)
- **FR15:** User can see a summary of detected entities (count per entity type) at the top of the sidebar
- **FR16:** System displays an AI limitation disclaimer advising the user to review all detections carefully

### Redaction

- **FR17:** User can trigger redaction of all confirmed (non-dismissed) PII entities
- **FR18:** System permanently removes confirmed PII text from the PDF data layer (true redaction, not cosmetic overlay)
- **FR19:** System renders black bars over redacted areas in the visual layer of the output PDF
- **FR20:** System strips PDF metadata (Author, Title, Subject, Creator, Producer) from the redacted output
- **FR21:** System strips XMP metadata from the redacted output
- **FR22:** System performs garbage collection to remove orphaned objects from the redacted output
- **FR23:** System saves the redacted PDF as a non-incremental write (no prior document versions preserved)
- **FR24:** System saves the redacted PDF as a new file with `_redacted` suffix, leaving the original untouched

### Temp File & Data Security

- **FR25:** System writes intermediate processing files to a secure OS temporary directory
- **FR26:** System deletes all temporary files immediately after producing the redacted output
- **FR27:** System scans for and deletes orphaned temporary files on launch (crash recovery)
- **FR28:** System makes zero network calls during document processing

### Ollama Lifecycle Management

- **FR29:** System checks whether Ollama is running and the Gemma 4 E4B model is loaded via `GET /api/tags` on `127.0.0.1:11434`. Displays "Ready" or "Please start Ollama with Gemma 4 E4B" accordingly.
- **FR30:** (Deferred to stretch) System starts Ollama as a subprocess if not running and triggers model download if missing. MVP requires Ollama to be pre-started by the user.
- **FR31:** System displays Ollama readiness status to the user (ready / not ready) on the main screen
- **FR32:** (Deferred to stretch) Download progress during first-launch model pull. MVP: user downloads model manually via `ollama pull gemma4:e4b` before launching.
- **FR33:** (Deferred to stretch) Subprocess lifecycle management. MVP does not manage Ollama process.
- **FR34:** UI shows a "100% local — no data leaves your machine" badge on the main screen

### Application Lifecycle

- **FR35:** User can launch the application from a localhost web interface opened in the default browser (MVP)
- **FR36:** User can access the application immediately after the Ollama/model readiness check completes
- **FR37:** System selects a random available port for the localhost web server to avoid conflicts

### Evaluation & Verification

- **FR38:** System includes an evaluation framework that measures precision, recall, and F1 per entity type against ground-truth annotated test documents
- **FR39:** System includes an automated redaction verification test that extracts text from redacted output and asserts zero PII matches
- **FR40:** Evaluation framework covers at least 5 test documents with French-language PII

## Non-Functional Requirements

### Performance

- **NFR1:** Single-page PDF completes the full pipeline (text extraction + per-block PII detection + validation + result display) in under 30 seconds on a machine with 8 GB RAM and no GPU
- **NFR2:** 10-page PDF completes the full pipeline in under 3 minutes under the same conditions
- **NFR3:** UI remains responsive during processing — no frozen screen. A spinner with status text ("Extracting…", "Detecting PII…", "Done") keeps the user informed.
- **NFR4:** (Deferred) Ollama cold start management. MVP assumes Ollama is already running with model loaded.
- **NFR5:** Redaction operation (apply_redactions + sanitization + save) completes in under 5 seconds for a 10-page document
- **NFR6:** Application startup (FastAPI server + browser open + Ollama readiness check) completes in under 5 seconds when Ollama is already running

### Security

- **NFR7:** Zero network calls during the entire document processing pipeline (text extraction, PII detection, redaction, save). Verifiable via network traffic monitoring.
- **NFR8:** No PII from processed documents is written to persistent storage except in the user-requested redacted output file. Temp files are deleted immediately after processing.
- **NFR9:** Redacted output contains zero extractable PII — verified by `pdftotext` text extraction returning no PII strings, PDF metadata fields returning empty, and XMP metadata absent
- **NFR10:** No telemetry, analytics, crash reporting, or usage logging that captures document content or PII
- **NFR11:** Temp files use OS-level restricted permissions (owner-only read/write) during processing
- **NFR12:** Orphaned temp files from prior crashes are detected and deleted on application launch

### Accessibility

- **NFR13:** Web interface follows basic semantic HTML structure (proper headings, labels, form elements) for screen reader compatibility
- **NFR14:** All interactive elements are keyboard-navigable (upload, review, dismiss, redact)
- **NFR15:** Color-coded highlights are supplemented with text labels so entity type information is not conveyed by color alone
- **NFR16:** UI text meets WCAG 2.1 AA contrast ratio (4.5:1 minimum for normal text)

Note: Full WCAG 2.1 AA compliance is a Phase 2 goal. MVP targets the four NFRs above as a baseline.

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Gemma 4 E4B accuracy insufficient for French NER | High | Low-Medium | Prompt engineering with few-shot examples; hybrid with spaCy as pre-filter; document limitations honestly |
| Per-block NER produces more Ollama calls, slower than whole-page approach | Medium | High | Per-block calls are smaller/faster individually; budget 2-3x performance targets; use short docs for demo |
| Gemma 4 hallucinates entity offsets that don't match source text | High | Medium | Post-detection validation step drops detections where text doesn't match at claimed offsets |
| Temp files persist after crash | High | Low | Cleanup routine on launch; OS temp directory with restricted permissions |
| Metadata not stripped from output PDF | High | Low | Sanitization pipeline strips metadata, XMP, runs garbage collection; automated test verifies |
| False negatives (missed PII) | High | Medium | Human-in-the-loop review mandatory; UI disclaimer; evaluation framework tracks recall |
| Font ToUnicode leaks character mappings | Medium | Low | Stretch: strip ToUnicode entries; document as known limitation if not implemented |
| Incremental save preserves pre-redaction state | High | Low | Non-incremental save (PyMuPDF default for new filename); stretch: pikepdf linearize |
| Local inference too slow on CPU | Medium | High | Budget 2-3x performance targets (30s/page, 3min/10-page); use short demo docs; spinner keeps UX responsive |
| True redaction fails on edge-case PDFs | Medium | Medium | Restrict MVP to single-column text-heavy PDFs; reject unsupported formats with clear error |
| Native `.app` packaging proves complex | Medium | Medium | Fallback: ship as localhost web app with launcher script |
| Time overrun due to day-job workload | Medium | Medium | Minimum submittable version defined; milestone gates enable scope cuts |
| "AI for AI safety" framing unclear in demo | Low | Medium | Video structure: problem (PII blocks AI adoption) → solution (AI removes PII) → proof (pdftotext verification) → impact (AI adoption unlocked safely) |
| Competition is stronger than expected | Low | Medium | Polish and storytelling differentiate; pdftotext verification proof is a unique demo moment |
| Day-job conflicts in final week | Medium | Medium | Video and write-up produced in evenings; core engineering complete 1 week before deadline |
