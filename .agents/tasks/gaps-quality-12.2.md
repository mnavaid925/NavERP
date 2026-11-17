# Gap Register — Sub-module 12.2: Design Controls & Development

**Module:** 12 — Quality Management System (`apps/quality/`)  
**Sub-module:** 12.2 — Design Controls & Development  
**Status:** COMPLETE (`23 / 23` review findings closed in [review-quality-12.2.md](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-quality-12.2.md); `231 / 231` dedicated 12.2 tests passing on SQLite, `356 / 356` total Quality suite passing; roadmap & upstream items tracked below)

---

## Gaps & Deferred Follow-Ups Inventory

### GAP-quality-12.2-01 — Cross-Module CAPA & Non-Conformance Hand-off on Verification Failure
- **Owner:** Quality Management (`apps/quality/`)
- **Waiting For / Blocked On:** Sub-module 12.3 (Non-Conformance Reports / NCR) and Sub-module 12.4 (Corrective & Preventive Actions / CAPA).
- **Status:** `[~]` Blocked on sibling sub-module development — `DesignVerification` correctly flags and logs test failures (`pass_fail_result="fail"`), automatically resets `primary_input.status` from `"verified"` to `"approved"`, and alerts the user; formal automated provisioning of an NCR ticket upon test failure will be linked when Sub-module 12.3 lands.
- **Done When:** A failed V&V test execution protocol (`pass_fail_result="fail"`) provides an action button to spawn a pre-filled Non-Conformance Report (`NonConformanceReport`) referencing the verification number and primary input.

### GAP-quality-12.2-02 — Formal Change Order (DCO) Workflow for Amending Frozen DHFs
- **Owner:** Quality Management / Regulatory (`quality`)
- **Waiting For / Blocked On:** Client workflow decision on DCO routing rules for Design History File unlocking.
- **Status:** `[~]` Deferred by design — 21 CFR § 820.30(j) and ISO 13485:7.3.10 immutable freeze is strictly enforced in code (`dhf_locked=True` prevents project edits, phase advance, child creation, and record mutations); formal integration with 12.1 `DocumentChangeOrder` (DCO) to approve post-market design modifications will be wired in a subsequent cross-feature pass.
- **Done When:** A locked project offers a "Request Design Change" action that initiates a `DocumentChangeOrder` with `change_type="design_change"`, unlocking the project only upon CCB approval.

### GAP-quality-12.2-03 — Automated Asynchronous PDF DHF Dossier Compilation Engine
- **Owner:** Quality Infrastructure / Document Pipeline (`quality` + `core`)
- **Waiting For / Blocked On:** Background task worker (Celery/Redis) with headless document renderer (e.g. WeasyPrint/ReportLab) to compile hundreds of linked specifications, protocols, and test attachments into a single paginated, bookmarked PDF file.
- **Status:** `[~]` Deferred by architecture — The audit-ready DHF Dossier web view (`design_project_dhf`) and streaming CSV export (`design_project_dhf_export`) are fully implemented and render all sections dynamically in real-time.
- **Done When:** An async task worker compiles all linked specifications, review minutes, and test execution protocols into an indexed, bookmarked PDF with table of contents.

### GAP-quality-12.2-04 — CAD / PLM Engineering Bill of Materials (EBOM) Artifact Integration
- **Owner:** Product Lifecycle Management / Quality (`plm` + `quality`)
- **Waiting For / Blocked On:** Module 15 (Product Lifecycle & Engineering Management — PLM).
- **Status:** `[~]` Blocked on upstream Module 15 — `DesignInput` supports direct linkage to `ControlledDocument` specifications; CAD file integration and 3D previewing will be bridged when Module 15 (PLM) lands.
- **Done When:** Design inputs can reference versioned CAD models and Engineering BOM items from Module 15.

---

## Completed Scope Note (`12.2` Deliverables)
- All `4` models (`DesignProject` `QDPL-`, `DesignInput` `QINP-`, `DesignReview` `QREV-`, `DesignVerification` `QVER-`), `4` ModelForms (`DesignProjectForm`, `DesignInputForm`, `DesignReviewForm`, `DesignVerificationForm`), `2` specialized workbenches (`TraceabilityMatrix`, `DHF Dossier`), `16` FBV views across 4 entities + workbenches, `10` templates, `LIVE_LINKS["12.2"]` (all 5 feature bullets), `apps/quality/admin.py`, `seed_quality` command extension (`_seed_submodule_12_2`), migrations `0003` & `0004`, and `231` dedicated unit/form/view/security tests (`356` total across `apps/quality/tests/`) are shipped and 100% green.
