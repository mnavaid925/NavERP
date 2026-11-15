# Gap Register — Sub-module 12.1: Document Control & Management

**Module:** 12 — Quality Management System (`apps/quality/`)  
**Sub-module:** 12.1 — Document Control & Management  
**Status:** COMPLETE (`33 / 33` review findings closed in [review-quality-12.1.md](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-quality-12.1.md); `125 / 125` dedicated 12.1 tests passing on SQLite; roadmap & upstream items tracked below)

---

## Gaps & Deferred Follow-Ups Inventory

### GAP-quality-12.1-01 — Office 365 / Google Workspace Real-Time Web Redlining Integration
- **Owner:** Quality Infrastructure / Document Management (`quality` + `documents`)
- **Waiting For / Blocked On:** WOPI (Web Application Open Platform Interface) host integration or Google Workspace Docs Add-on architecture for in-browser collaborative redlining and track-changes review of DOCX files.
- **Status:** `[~]` Deferred by architecture (`contract-quality-12.1.md` & `.claude/tasks/todo.md`) — Document metadata, revision history, and controlled file uploads/downloads with strict extension checking (`ALLOWED_DOC_EXTENSIONS`) and size caps (`MAX_UPLOAD_BYTES`) are fully operational and isolated.
- **Done When:** WOPI client endpoint provides secure iframe embedding allowing concurrent redlining and saves finalized revisions directly back to `ControlledDocument`.

### GAP-quality-12.1-02 — Hardware PKI / Smart Card Token Signing (X.509 / PIV / CAC)
- **Owner:** Security & Compliance / Cryptography (`quality` + `core`)
- **Waiting For / Blocked On:** WebCrypto / PKCS#11 browser certificate extension or client-side smartcard daemon for hardware cryptographic key signing.
- **Status:** `[~]` Deferred by design — Dual-credential authentication (`password` re-check per FDA 21 CFR § 11.200) and RFC 2104 compliant HMAC-SHA256 signature hashing are fully implemented in `ElectronicSignatureForm` and `ElectronicSignatureRecord`.
- **Done When:** Hardware smartcard challenge-response signature is appended to `ElectronicSignatureRecord.verification_hash`.

### GAP-quality-12.1-03 — Asynchronous In-Flight PDF Dynamic Watermarking Engine
- **Owner:** Quality Backend / Worker Pipeline (`quality` + `core`)
- **Waiting For / Blocked On:** Celery/Redis worker background pipeline for stamping dynamic diagonal watermarks ("DRAFT", "EFFECTIVE - CONTROLLED COPY", "OBSOLETE") onto binary PDF pages at download time.
- **Status:** `[~]` Deferred by design — Dynamic visual watermarks are rendered across all web UI templates, vault views, and print stylesheets via `document.watermark_text`.
- **Done When:** Download handler intercepts PDF file requests and streams dynamically stamped watermarked PDFs via PyMuPDF/ReportLab.

### GAP-quality-12.1-04 — Cross-Module GxP CAPA & Change Control Hand-off
- **Owner:** Quality Management (`apps/quality/`)
- **Waiting For / Blocked On:** Sub-module 12.4 (CAPA Management) and Sub-module 12.5 (Non-Conformance Management).
- **Status:** `[~]` Blocked on sibling sub-module development — `DocumentChangeOrder` supports `regulatory_impact` and change triage; formal bidirectional linking to CAPA action plans will be linked when Module 12.4 lands.
- **Done When:** Sub-module 12.4 CAPA records can spawn linked `DocumentChangeOrder` instances upon root-cause determination.

---

## Completed Scope Note (`12.1` Deliverables)
- All `4` models (`ControlledDocument` `QDOC-`, `DocumentChangeOrder` `QDCR-`, `ElectronicSignatureRecord` `QSIG-`, `DocumentAcknowledgment` `QACK-`), `6` ModelForms (`ControlledDocumentForm`, `ControlledDocumentRevisionForm`, `DocumentChangeOrderForm`, `DocumentChangeOrderReviewForm`, `CCBDecisionForm`, `DocumentAcknowledgmentForm`), `1` Part 11 signature Form (`ElectronicSignatureForm`), `31` FBV views across 4 entities + vault workbench, `13` templates, `LIVE_LINKS["12.1"]` (all 5 feature bullets), `apps/quality/admin.py`, `seed_quality`, migrations `0001` & `0002`, and `125` dedicated unit/form/view/security tests are shipped and 100% green.
