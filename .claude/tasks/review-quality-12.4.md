# Review Findings — Sub-module 12.4: Corrective & Preventive Action (CAPA) (Module 12 — Quality Management System, `quality`)

**Changeset reviewed**: `9af088e4e44aaad583908e20fa419f1afc32b61c...HEAD`
**Target App**: `apps/quality/` (Sub-module 12.4: `CapaManagement/`) and `templates/quality/capamanagement/`
**Date**: 2026-11-17

All six review passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) have concluded strictly serially. Below is the deduplicated, consolidated, and prioritized action register for Phase 5 (`code-fixer`).

---

## Consolidated Action Register

### Critical Findings

- [x] **C1**: `apps/quality/views/CapaManagement/CapaInvestigations.py:183-194` — Privilege Escalation & AuthZ Lifecycle Guard Bypass in `capa_investigation_advance_status`. Permits arbitrary transition to `"closed"` via raw POST without `@tenant_admin_required`, incomplete actions checks (`pending_actions > 0`), and closure metadata timestamps. Also permits non-admins to void CAPAs, and permits closed records to be reopened.
  - *Fix*: In `capa_investigation_advance_status`: block transitions if `capa.status == "closed"`; disallow `target_status="closed"` (directing users to `capa_investigation_close`); and require `request.user.is_tenant_admin` if `target_status == "voided"`.
  - *Status*: [x] fixed — a67cfc19: fix(quality): guard capa investigation advance status against closed transitions and non-admin voiding

- [x] **C2**: `apps/quality/views/CapaManagement/CapaEffectivenessReviews.py:160-174` — Recurrence Guard Bypass & Missing Evaluator Gate in `capa_effectiveness_review_sign_off`. Allows marking an effectiveness review as `"effective"` even when `review.recurrence_observed` is `True`, bypassing the mandatory safety rule enforced in `CapaEffectivenessReviewForm.clean()`. Also lacks guard against re-signing completed reviews and lacks check that user is assigned evaluator or tenant admin.
  - *Fix*: In `capa_effectiveness_review_sign_off`: guard `if review.status == "completed"`; check `if request.user != review.evaluator and not request.user.is_tenant_admin: error(...)`; and check `if review.recurrence_observed and outcome == "effective": error(...)`.
  - *Status*: [x] fixed — 9d3c18c0: fix(quality): guard capa effectiveness review sign off against recurrence and unauthorized evaluator

- [x] **C3**: `apps/quality/forms/CapaManagement/` (`CapaInvestigations.py:35`, `RootCauseAnalyses.py:32`, `CapaActions.py:28`, `CapaEffectivenessReviews.py:24`) — Mass Assignment of Workflow-Controlled `status` across all four CAPA ModelForms. Exposing `status` in `Meta.fields` allows users to submit terminal/verified/closed statuses via standard create/edit forms.
  - *Fix*: In form `clean_status()` methods across all four forms: disallow transitioning to closed/voided/verified/completed via basic create/edit forms unless instance already has that status.
  - *Status*: [x] fixed — d46754ff, f32c3b68, 212447a6, cc0a9d00: disallow setting terminal/controlled statuses directly in CapaInvestigationForm, RootCauseAnalysisForm, CapaActionForm, CapaEffectivenessReviewForm

- [x] **C4**: `apps/quality/models/CapaManagement/` (`CapaInvestigations.py:47,74`, `RootCauseAnalyses.py:42,50,58`, `CapaActions.py:28`, `CapaEffectivenessReviews.py:35`) — Non-existent theme badge class `"badge-purple"` (Lesson L33 / theme.css design system contract). `theme.css` defines only `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`. When any of these choices are rendered, badges render unstyled.
  - *Fix*: Replace `"badge-purple"` entries with valid theme palette classes (e.g., `"badge-info"` or `"badge-slate"`).
  - *Status*: [x] fixed — c7da35e1, abdae17c, fc86f85c, 83cd4052: replace non-existent badge-purple with valid theme badge classes across all 4 CAPA models

- [x] **C5**: `apps/quality/models/CapaManagement/CapaInvestigations.py:191-197`, `apps/quality/views/CapaManagement/CapaInvestigations.py:30-33`, and `templates/quality/capamanagement/capa_investigation/list.html:171-175` — Severe N+1 Queries in `capa_investigation_list` via unannotated model property evaluations (`capa.actions_count` and `capa.pending_actions_count`), causing up to 45 extra queries per 15-row page. Because `@property` is a class data descriptor, annotating the queryset alone will not override the property unless the property explicitly checks `if 'actions_count' in self.__dict__`.
  - *Fix*: Update properties in `CapaInvestigations.py` to check `self.__dict__` first, annotate `actions_count` and `pending_actions_count` on `qs` in `capa_investigation_list`.
  - *Status*: [x] fixed — ded391c0, 9cab367e: check __dict__ in model properties & annotate actions_count and pending_actions_count in capa_investigation_list

---

### Important Findings

- [x] **I1**: `apps/quality/views/CapaManagement/CapaInvestigations.py:168-175`, `RootCauseAnalyses.py:148-156`, `CapaActions.py:158-167`, `CapaEffectivenessReviews.py:141-150` — Missing Status & Audit Trail Deletion Guards in Delete Views. Allows POST deletion of closed CAPAs (cascade-deleting child regulatory audit trails), verified RCAs, verified actions, and completed effectiveness reviews.
  - *Fix*: Add status guards in all four delete views (e.g. `if capa.status == "closed": messages.error(...)`, and disallow deleting verified/completed child records).
  - *Status*: [x] fixed — 50332975, b5ba8315, 010994a7, 00563337: add status & audit trail deletion guards to all 4 delete views

- [x] **I2**: `apps/quality/forms/CapaManagement/CapaActions.py:69-84` — Cross-Record Integrity Bypass in `CapaActionForm` (Cross-CAPA Root Cause Association). Form verifies foreign keys belong to tenant, but never checks `root_cause.capa_id == capa.id`.
  - *Fix*: In `CapaActionForm.clean()`, validate `if cleaned.get("root_cause") and cleaned.get("capa") and cleaned["root_cause"].capa_id != cleaned["capa"].id: self.add_error("root_cause", ...)`.
  - *Status*: [x] fixed — 7470835e: enforce root cause analysis belongs to selected CAPA in CapaActionForm

- [x] **I3**: `templates/quality/capamanagement/capa_investigation/detail.html:24-43`, `root_cause_analysis/detail.html:26-39`, `capa_action/detail.html:24-35`, `capa_effectiveness_review/detail.html:26-36` — All 4 detail templates lack the status-conditional POST Delete form in the `.page-actions` header, violating the CLAUDE.md CRUD navigation contract (`Edit / POST-Delete / Back-to-List`).
  - *Fix*: Add status-conditional POST-delete forms with `{% csrf_token %}`, confirm prompt, and `btn btn-danger` or `btn-outline text-red-600` to all 4 detail template headers.
  - *Status*: [x] fixed — f88758be, 5e716311, 885edcbb, f730471d: add status-conditional POST delete button to all 4 detail headers

- [x] **I4**: `templates/quality/capamanagement/` (`capa_investigation/list.html:185-190`, `root_cause_analysis/list.html:146-150`, `capa_action/list.html:155-160`, `capa_effectiveness_review/list.html:157-162`, `capa_investigation/detail.html:280-288`) — Unauthorized UI Action Exposure: Delete and Formal Closure Forms Unconditionally Offered to Non-Admin Users (resulting in HTTP 403 on Submit).
  - *Fix*: Wrap delete forms in list templates and the formal closure form in `capa_investigation/detail.html` with `{% if request.user.is_tenant_admin %}`.
  - *Status*: [x] fixed — 18fc79c0, ade6bf07, d2dfc1af, e2d56a96, 7335a487: gate list delete buttons and formal closure form to tenant admin

- [x] **I5**: `apps/quality/views/CapaManagement/` (`RootCauseAnalyses.py:67-76`, `CapaActions.py:70-80`, `CapaEffectivenessReviews.py:65-75`), and matching `list.html` pagination blocks — Parent `capa` GET filter is dropped during pagination because `capa_filter` is omitted from view context dicts and pagination links (`<a href="?page=...">`), resetting to unfiltered listings past page 1.
  - *Fix*: Pass `capa_filter` into context across all three list views and include `{% if capa_filter %}&capa={{ capa_filter }}{% endif %}` in the pagination query strings.
  - *Status*: [x] fixed — e98286d0, ff5d3c18, 68f5fe18, d4f329a1, 2d2ebac1, b929810c: pass capa_filter to context and preserve in pagination query strings across all 3 child entities

- [x] **I6**: `apps/quality/{models,forms,views,urls}/CapaManagement/` — Missing `__init__.py` in all 4 `CapaManagement` subpackages, violating CLAUDE.md backend package conventions and consistency with sibling sub-modules.
  - *Fix*: Create and commit empty `__init__.py` in all 4 subdirectories (`models/CapaManagement/`, `forms/CapaManagement/`, `views/CapaManagement/`, `urls/CapaManagement/`).
  - *Status*: [x] fixed — 2d76dff1, b3e98921, 92a5c769, 353b4c24: add empty __init__.py to models, forms, views, and urls CapaManagement subpackages

- [x] **I7**: `apps/quality/forms/CapaManagement/CapaActions.py:54`, `apps/quality/models/CapaManagement/RootCauseAnalyses.py:126-128` — Chained N+1 Foreign Key query burst in `CapaActionForm` choice rendering through `RootCauseAnalysis.__str__` (Lesson L18). In `CapaActionForm`, `self.fields["root_cause"].queryset` lacks `.select_related("capa")`.
  - *Fix*: Add `.select_related("capa")` to `self.fields["root_cause"].queryset`.
  - *Status*: [x] fixed — 2da2c88c: select_related capa for root_cause queryset in CapaActionForm

- [x] **I8**: `apps/quality/models/CapaManagement/CapaInvestigations.py:163-169`, `apps/quality/models/CapaManagement/CapaActions.py:110-116` — Missing compound tenant composite indexes for hot filter dimensions: `(tenant, action_type)` and `(tenant, department)`.
  - *Fix*: Add `models.Index(fields=["tenant", "action_type"], name="idx_qcap_ten_act_type")`, `models.Index(fields=["tenant", "department"], name="idx_qcap_ten_dept")` on `CapaInvestigation`, and `models.Index(fields=["tenant", "department"], name="idx_qact_ten_dept")` on `CapaAction`. Generate and run migration.
  - *Status*: [x] fixed — 408793be, df3af89a, acc964b1: add composite indexes to CapaInvestigation and CapaAction, generated and migrated quality.0008

- [x] **I9**: `templates/quality/capamanagement/capa_investigation/detail.html:290-298` & `templates/quality/capamanagement/capa_effectiveness_review/detail.html:97-104` — Missing Electronic Signature display in detail templates for 21 CFR Part 11 regulatory compliance.
  - *Fix*: Add conditional display blocks in both detail templates rendering signer name and signed timestamp when present.
  - *Status*: [x] fixed — 8badc181, 6964dbb8: display Part 11 electronic signature on closed CAPA detail and completed review detail

- [x] **I10**: `apps/quality/views/CapaManagement/CapaActions.py:187-202` & `RootCauseAnalyses.py:159-174` — Missing State Validation & Separation of Duties on Verification Actions. `capa_action_verify` allows verifying non-implemented actions and allows assignee to verify their own action; `root_cause_analysis_verify` lacks check against re-verifying already verified RCA.
  - *Fix*: Enforce `action.status == "implemented"`, guard against re-verification, and require verification by someone other than assignee (unless tenant admin).
  - *Status*: [x] fixed — d1840c7a, 9f154bd5: enforce implemented status, separation of duties, and re-verification guards on Action and RCA verification

- [x] **I11**: `apps/quality/views/CapaManagement/CapaTrackingBoard.py:25-31` — Unused table joins and unconstrained heavy TextField loading in `capa_tracking_board`.
  - *Fix*: Remove unused `select_related("lead_investigator", "quality_owner", "department")` and add `.only(...)` with required fields.
  - *Status*: [x] fixed — 6daebed5: optimize capa_tracking_board query removing unused joins and deferring heavy textfields

- [x] **I12**: `apps/quality/views/CapaManagement/CapaTrackingBoard.py:128` — Unsaved model instance `CapaInvestigation()` passed to `write_audit_log` on tracking board export.
  - *Fix*: Log export against `request.tenant` (`write_audit_log(request.user, request.tenant, "export", tenant=request.tenant)`).
  - *Status*: [x] fixed — 72959d20: pass tenant instance to write_audit_log on tracking board export

---

### Minor Findings

- [x] **M1**: `templates/quality/capamanagement/` (`capa_investigation/form.html:8-16`, `root_cause_analysis/form.html:8-18`, `capa_action/form.html:8-18`, `capa_effectiveness_review/form.html:8-18`) — Breadcrumb hierarchy omission: all 4 form templates omit `<span>Quality Management</span> <span>/</span>`.
  - *Fix*: Standardize breadcrumbs across all 4 form templates.
  - *Status*: [x] fixed — 99348f8d, e5d1d25e, 2f28746d, 564cac97: add Quality Management to breadcrumbs across all 4 form templates

- [x] **M2**: `templates/quality/capamanagement/capa_action/detail.html:56` — Substring status comparison `in 'implemented verified'`.
  - *Fix*: Replace with `{% if action.status == 'implemented' or action.status == 'verified' %}`.
  - *Status*: [x] fixed — a638539e: replace substring status check with exact equality in Action detail

- [x] **M3**: `templates/quality/capamanagement/capa_investigation/detail.html:293` — Unprotected nullable FK attribute access on `capa.closure_approved_by.username` (Lesson L10).
  - *Fix*: Wrap in `{% if capa.closure_approved_by %}` or use `|default:"System / Unassigned"`.
  - *Status*: [x] fixed — d7ed2e4b: guard closure_approved_by against None in CAPA detail

- [x] **M4**: `templates/quality/capamanagement/capa_investigation/detail.html:180, 236` — Icon-only action links missing `title` attribute for tooltips and accessibility.
  - *Fix*: Add `title="View Action"` and `title="View Review"`.
  - *Status*: [x] fixed — 03cfe740: add title attributes to icon-only action links in CAPA detail

- [x] **M5**: `templates/quality/capamanagement/root_cause_analysis/detail.html:68, 74, 80, 86` & `capa_tracking_board.html:76, 100` — Physical margins `ml-*` and `border-l-*` instead of logical `ms-*` and `border-s-*` for RTL adaptability.
  - *Fix*: Replace with logical classes `ms-*` and `border-s-*`.
  - *Status*: [x] fixed — e0683be7, 4e0afa42: use logical ms- and border-s- classes in RCA detail and tracking board

- [x] **M6**: `apps/quality/models/CapaManagement/CapaInvestigations.py:211-213` — `days_open` property assumes `self.created_at` is always populated; accessing it on an unsaved model instance will raise `AttributeError`.
  - *Fix*: Add initial guard `if not self.created_at: return 0`.
  - *Status*: [x] fixed — b8668768: guard days_open property against unsaved instances without created_at

- [x] **M7**: `apps/quality/views/CapaManagement/CapaActions.py:171-184` — `capa_action_mark_completed` does not guard against resetting already `verified` or `cancelled` actions back to `implemented`.
  - *Fix*: Add guard `if action.status in ["verified", "cancelled"]: messages.warning(...); return redirect(...)`.
  - *Status*: [x] fixed — 47196821: guard capa_action_mark_completed against resetting verified or cancelled actions

- [x] **M8**: `apps/quality/forms/CapaManagement/` (`RootCauseAnalyses.py:15`, `CapaActions.py:20`, `CapaEffectivenessReviews.py:15`) — Child Model Reassignment Across Parent CAPAs on Edit.
  - *Fix*: Validate immutability of `capa` on instance update in `clean()`.
  - *Status*: [x] fixed — 2ee5edc0, dd170c5b, 45362dea: enforce parent CAPA immutability on RCA, Action, and Review updates

---

## Detailed Review Passes

### Pass 1: Code Reviewer (`code-reviewer`)
- Reviewed `BASE...HEAD`: checked multi-tenancy, decorators, FBVs, audit logging, model choices, form validation, and export endpoints.
- Reported CR-C1, CR-C2, CR-I1 through CR-I5, CR-M1, CR-M2.

### Pass 2: Explorer Review (`explorer`)
- Reviewed URL routing, reverse resolution, view context contracts against `contract-quality-12.4.md`, breadcrumbs, package structure, and spine reuse.
- Reported EX-I1 through EX-I3, EX-M1, EX-M2.

### Pass 3: Frontend Review (`frontend-reviewer`)
- Reviewed 13 templates: comment leak check (0 leaks), theme color-named badges, CRUD buttons, pagination guards, None-safe access, accessibility.
- Reported FE-C1, FE-I1, FE-I2, FE-M1, FE-M2.

### Pass 4: Performance Review (`performance-reviewer`)
- Reviewed ORM query efficiency: N+1 queries, chained `__str__` lookups, property descriptor trap on `actions_count`, KPI aggregates, tracking board queries, composite indexing.
- Reported PRF-C1, PRF-I1 through PRF-I3, PRF-M1.

### Pass 5: QA Smoke Tester (`qa-smoke-tester`)
- Executed 74 test client cases across Acme & Globex tenants: list, detail, create, edit, export, lifecycle POSTs, junk filters, IDOR.
- Confirmed zero 500 errors, verified 18/18 IDOR 404s, confirmed runtime reproduction of CR-C1, CR-C2, and FE-C1.
- Reported QA-C1 through QA-C3, QA-I1, QA-I2, QA-M1.

### Pass 6: Security Reviewer (`security-reviewer`)
- Audited multi-tenant isolation, IDOR, authorization gates, mass assignment of workflow `status`, cross-record integrity, CSV injection safety, CSRF.
- Reported SEC-C1 through SEC-C3, SEC-I1 through SEC-I4, SEC-M1, SEC-M2.
