# Module 11.16 Gap Register — Asset Document & Knowledge Management

- **Sub-module**: `11.16 Document & Knowledge Management` (`apps/assets`, package `AssetDocumentKnowledge`)
- **Review File**: `.claude/tasks/review-assets-11.16.md` (0 `[ ] open`, all 32 items `[x] fixed`)
- **In-Scope Gaps**: None (all `11.16` contract items, review findings, migrations, UI polish, security controls, and 110 unit/form/view/security tests completed and passing inside `apps/assets`).
- **Deferred / Cross-Module & Sibling Observations**:

---

### GAP-assets-11.16-01 — Enforcing `is_operator_certified()` Gate inside `11.5` & `11.13` Work Order Dispatch
- **Owner**: `assets` (Maintenance `11.5` & Mobile `11.13` pass)
- **Waiting For / Blocked On**: Cross-sub-module workflow alignment and technician dispatch UX policy without altering sibling `11.5` (`AssetMaintenanceRequest`) / `11.13` (`FieldWorkOrder`) code in this `11.16` pass.
- **Status**: `- [~]` Deferred — `AssetOperatorCertification.is_operator_certified(...)` API (with both `asset_category` FK and `scm.Asset.category` fallback) is built and tested in `11.16`; call sites inside `11.5`/`11.13` assignment views are deferred.
- **Done When**: `AssetMaintenanceRequest` and `FieldWorkOrder` technician assignment/dispatch views validate `is_operator_certified()` for procedures/assets requiring certification (or display an override warning/audit entry) with regression tests in `11.5`/`11.13` suites.

---

### GAP-assets-11.16-02 — Scheduled Background Expiry & Safety-Review Notifications
- **Owner**: `assets` / platform notification scheduler
- **Waiting For / Blocked On**: Asynchronous worker/cron scheduler adoption (`Celery` / management cron + tenant notification channel preferences).
- **Status**: `- [~]` Deferred — Synchronous `@tenant_admin_required` `refresh_alerts` bulk-update endpoint is built and tested in `11.16`; scheduled background email/in-app dispatch is deferred.
- **Done When**: A scheduled task runs `sync_expiry_status` per tenant and dispatches notifications for `expiring_soon`/`expired` certifications, expiring `AssetDocument`s, and overdue `AssetOperatingProcedure` `next_review_date` deadlines.

---

### GAP-assets-11.16-03 — OCR PDF Indexing, Interactive CAD/DWG Redlining & 21 CFR Part 11 Watermarking
- **Owner**: `documents` (Module 13) / `quality` (Module 12) / future `assets` `11.17`–`11.19` passes
- **Waiting For / Blocked On**: Document Management System (`Module 13`), QMS e-signature infrastructure (`Module 12`), and CAD/BIM viewer sub-modules.
- **Status**: `- [~]` Deferred — Out of `11.16` scope per `.claude/tasks/research-assets-11.16.md` & `todo.md`.
- **Done When**: PDF full-text OCR search, canvas CAD markup overlays, and re-authenticated Part 11 signature/watermarking pipelines are implemented in their owning modules and linked to `AssetDocument`.

---

### GAP-assets-11.16-04 — Sibling Clone Observation: `AssetAnalytics/_helpers.py:apply_choice_filter`
- **Owner**: `assets` (`11.14` Asset Analytics cleanup pass)
- **Waiting For / Blocked On**: Dedicated `11.14` pass (`11.16` `code-fixer` fixed `AssetDocumentKnowledge/_helpers.py` `apply_choice_filter` per `I4` and left `AssetAnalytics/_helpers.py:22-29` untouched to respect diff scope).
- **Status**: `- [ ]` Open — Out-of-scope clone observation in sibling `apps/assets/views/AssetAnalytics/_helpers.py:22-29` where unrecognized GET choice parameters return `qs.none()` instead of ignoring invalid values cleanly (L11).
- **Done When**: `apps/assets/views/AssetAnalytics/_helpers.py:apply_choice_filter` ignores unrecognized GET choice params (returns `qs` unchanged) with an accompanying unit/view test in `11.14`.
