# Review Findings — Sub-module 12.4: Corrective & Preventive Action (CAPA) (Module 12 — Quality Management System, `quality`)

**Changeset reviewed**: `9af088e4e44aaad583908e20fa419f1afc32b61c...HEAD`
**Target App**: `apps/quality/` (Sub-module 12.4: `CapaManagement/`) and `templates/quality/capamanagement/`
**Date**: 2026-11-17

All six review passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) run strictly serially. Below are the findings appended pass-by-pass, to be consolidated into an action register for Phase 5 (`code-fixer`).

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
- **CR-C1**: `apps/quality/views/CapaManagement/CapaInvestigations.py:183-194` — `capa_investigation_advance_status` permits arbitrary transition to `"closed"` via POST, bypassing `@tenant_admin_required`, incomplete actions checks, and closure metadata timestamps, while also permitting closed records to be reopened to draft without authorization.
  - *Fix*: Disallow `target_status="closed"` in `capa_investigation_advance_status` (directing users to `capa_investigation_close`), block transitions if `capa.status == "closed"` (or gate behind tenant admin), and require `request.user.is_tenant_admin` if `target_status == "voided"`.
- **CR-C2**: `apps/quality/views/CapaManagement/CapaEffectivenessReviews.py:160-174` — `capa_effectiveness_review_sign_off` allows marking an effectiveness review as `"effective"` even when `review.recurrence_observed` is `True`, bypassing the mandatory safety rule enforced in `CapaEffectivenessReviewForm.clean()`, and lacks a guard against re-signing completed reviews.
  - *Fix*: In `capa_effectiveness_review_sign_off`, check `if review.recurrence_observed and outcome == "effective": messages.error(request, "Cannot sign off review as 'Effective' when recurrence has been observed."); return redirect(...)`, and guard against `review.status == "completed"`.

### Important
- **CR-I1**: `apps/quality/views/CapaManagement/CapaInvestigations.py:168-175`, `RootCauseAnalyses.py:148-156`, `CapaActions.py:158-167`, `CapaEffectivenessReviews.py:141-150` — Delete views lack view-level status guards, allowing POST deletion of closed CAPAs (cascade-deleting child regulatory audit trails), verified RCAs, verified actions, and completed effectiveness reviews.
  - *Fix*: Add status guards in all four delete views (e.g. `if capa.status == "closed": messages.error(...); return redirect(...)`, and disallow deleting verified/completed child records).
- **CR-I2**: `apps/quality/forms/CapaManagement/CapaActions.py:69-84` — `CapaActionForm.clean()` verifies foreign keys belong to the tenant, but never verifies that `root_cause.capa_id == capa.id`, allowing cross-CAPA root cause associations.
  - *Fix*: In `CapaActionForm.clean()`, validate:
    ```python
    if cleaned.get("root_cause") and cleaned.get("capa"):
        if cleaned["root_cause"].capa_id != cleaned["capa"].id:
            self.add_error("root_cause", "The selected root cause does not belong to this CAPA investigation.")
    ```
- **CR-I3**: `templates/quality/capamanagement/capa_investigation/detail.html:24-43`, `root_cause_analysis/detail.html:26-39`, `capa_action/detail.html:24-35`, `capa_effectiveness_review/detail.html:26-36` — All four detail pages omit the status-conditional POST-only Delete form with CSRF and confirm prompt from their header actions sidebar, violating the CLAUDE.md Section 6 CRUD contract.
  - *Fix*: Add status-conditional POST delete form buttons with `{% csrf_token %}` and confirm prompts to the actions header of all four detail templates.
- **CR-I4**: `apps/quality/views/CapaManagement/RootCauseAnalyses.py:67-76`, `CapaActions.py:70-80`, `CapaEffectivenessReviews.py:65-75`, and matching `list.html` pagination blocks — Parent `capa` GET filter is dropped during pagination because `capa_filter` is omitted from view context dicts and pagination links (`<a href="?page=...">`), resetting to unfiltered listings past page 1.
  - *Fix*: Pass `capa_filter` into context across all three list views and include `{% if capa_filter %}&capa={{ capa_filter }}{% endif %}` in the pagination query strings.
- **CR-I5**: `apps/quality/models/CapaManagement/CapaInvestigations.py:47,74`, `RootCauseAnalyses.py:42,50,58`, `CapaActions.py:28`, `CapaEffectivenessReviews.py:35` — Badge CSS mapping dictionaries use `"badge-purple"`, which is not defined in `static/css/theme.css` and violates the fixed color-named badge contract (Lesson L33), causing these badges to render unstyled.
  - *Fix*: Replace `"badge-purple"` entries with valid theme palette classes such as `"badge-info"`, `"badge-slate"`, or `"badge-amber"`.

### Minor
- **CR-M1**: `apps/quality/views/CapaManagement/CapaActions.py:171-202` — `capa_action_mark_completed` does not guard against resetting already verified or cancelled actions, and `capa_action_verify` does not enforce that actions must be in `implemented` status prior to verification.
  - *Fix*: In `capa_action_mark_completed`, add `if action.status in ["verified", "cancelled"]: messages.warning(...); return redirect(...)`; in `capa_action_verify`, check `if action.status != "implemented": messages.warning(request, "Only implemented actions can be verified."); return redirect(...)`.
- **CR-M2**: `apps/quality/models/CapaManagement/CapaInvestigations.py:211-213` — `days_open` property assumes `self.created_at` is always populated; accessing it on an unsaved model instance will raise `AttributeError`.
  - *Fix*: Add an initial guard `if not self.created_at: return 0`.

---

## Pass 2: Explorer Review (`explorer`)

### Important
- **EX-I1**: `apps/quality/{models,forms,views,urls}/CapaManagement/` — Missing `__init__.py` in all 4 `CapaManagement` subpackages. While Python 3.3+ supports implicit namespaces, this violates CLAUDE.md backend package conventions ("Backend layers are PACKAGES, one folder per sub-module, one file per entity... Empty `__init__.py` files still get their own commit"), breaks uniformity with sibling sub-modules, and can cause issues with static analyzers and packaging.
  - *Fix*: Create and commit empty `__init__.py` files in `apps/quality/models/CapaManagement/`, `forms/CapaManagement/`, `views/CapaManagement/`, and `urls/CapaManagement/`.
- **EX-I2**: `apps/quality/views/CapaManagement/CapaInvestigations.py:29-33` & `templates/quality/capamanagement/capa_investigation/list.html:171-175` — N+1 queries in `capa_investigation_list` for action counts (`capa.pending_actions_count` and `capa.actions_count` evaluated per row in template).
  - *Fix*: In `capa_investigation_list`, annotate `actions_count=Count('actions')` and `pending_actions_count=Count('actions', filter=~Q(actions__status__in=['implemented', 'verified', 'cancelled']))` on `qs`.
- **EX-I3**: `templates/quality/capamanagement/capa_investigation/detail.html:290-298` & `templates/quality/capamanagement/capa_effectiveness_review/detail.html:97-104` — Missing Electronic Signature display in detail templates. Both models have FKs to `quality.ElectronicSignatureRecord` for 21 CFR Part 11 regulatory compliance, but neither detail template renders the attached e-signature manifest.
  - *Fix*: Add conditional display blocks in both detail templates rendering signer name and signed timestamp.

### Minor
- **EX-M1**: `templates/quality/capamanagement/capa_investigation/form.html:8-16`, `root_cause_analysis/form.html:8-18`, `capa_action/form.html:8-18`, `capa_effectiveness_review/form.html:8-18` — Breadcrumb hierarchy omission: all 4 form templates omit the `<span>Quality Management</span> <span>/</span>` breadcrumb segment.
  - *Fix*: Standardize breadcrumbs across all 4 form templates to include `<span>Quality Management</span> <span>/</span>`.
- **EX-M2**: `templates/quality/capamanagement/capa_action/detail.html:56` — Substring status comparison `in 'implemented verified'`.
  - *Fix*: Replace with `{% if action.status == 'implemented' or action.status == 'verified' %}`.

---

## Pass 3: Frontend Review (`frontend-reviewer`)

### Critical
- **FE-C1**: `apps/quality/models/CapaManagement/` (`CapaInvestigations.py:47,74`, `CapaActions.py:28`, `CapaEffectivenessReviews.py:35`, `RootCauseAnalyses.py:42,50,58`) — Non-existent theme badge class `"badge-purple"` (Lesson L33 / theme.css design system guard). `theme.css` defines only `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`. When any of these choices are rendered in list/detail/board templates, badges render unstyled.
  - *Fix*: Update model dictionary mappings to use valid theme palette classes (e.g., `"badge-info"` or `"badge-slate"`).

### Important
- **FE-I1**: `templates/quality/capamanagement/capa_investigation/detail.html:24-43`, `root_cause_analysis/detail.html:26-39`, `capa_action/detail.html:25-35`, `capa_effectiveness_review/detail.html:26-36` — All 4 detail templates lack the status-conditional POST Delete form in the `.page-actions` header, violating the CLAUDE.md CRUD navigation contract (`Edit / POST-Delete / Back-to-List`).
  - *Fix*: Add POST-delete forms with `{% csrf_token %}`, confirm prompt, and `btn btn-danger` or `btn-outline text-red-600` to all 4 detail template headers.
- **FE-I2**: `templates/quality/capamanagement/capa_investigation/detail.html:293` — Unprotected nullable FK attribute access on `capa.closure_approved_by.username` (Lesson L10).
  - *Fix*: Use `{{ capa.closure_approved_by.username|default:"System / Unassigned" }}` or wrap in `{% if capa.closure_approved_by %}`.

### Minor
- **FE-M1**: `templates/quality/capamanagement/capa_investigation/detail.html:180, 236` — Icon-only action links missing `title` attribute for tooltips and accessibility.
  - *Fix*: Add `title="View Action"` and `title="View Review"`.
- **FE-M2**: `templates/quality/capamanagement/root_cause_analysis/detail.html:68, 74, 80, 86` & `capa_tracking_board.html:76, 100` — Physical margins `ml-*` and `border-l-*` instead of logical `ms-*` and `border-s-*` for RTL adaptability.
  - *Fix*: Replace with `ms-3`, `ms-6`, etc. and `border-s-4`.

---

## Pass 4: Performance Review (`performance-reviewer`)

### Critical
- **PRF-C1**: `apps/quality/models/CapaManagement/CapaInvestigations.py:191-197`, `apps/quality/views/CapaManagement/CapaInvestigations.py:30-33`, and `templates/quality/capamanagement/capa_investigation/list.html:171-175` — N+1 Queries in `capa_investigation_list` via unannotated model property evaluations (`capa.actions_count` and `capa.pending_actions_count`), causing up to 45 extra queries per 15-row page. Because `@property` is a class data descriptor, annotating the queryset alone will not override the property unless the property explicitly checks `if 'actions_count' in self.__dict__`.
  - *Fix*: Update properties in `CapaInvestigations.py` to check `self.__dict__` first, annotate `actions_count` and `pending_actions_count` on `qs` in `capa_investigation_list`, and assert max queries in tests.

### Important
- **PRF-I1**: `apps/quality/forms/CapaManagement/CapaActions.py:54`, `apps/quality/models/CapaManagement/RootCauseAnalyses.py:126-128` — Chained N+1 Foreign Key query burst in `CapaActionForm` choice rendering through `RootCauseAnalysis.__str__` (Lesson L18). In `CapaActionForm`, `self.fields["root_cause"].queryset` lacks `.select_related("capa")`, triggering a query per RCA in the tenant on form load.
  - *Fix*: Add `.select_related("capa")` to `self.fields["root_cause"].queryset`.
- **PRF-I2**: `apps/quality/views/CapaManagement/CapaTrackingBoard.py:25-31` — Unused table joins and unconstrained heavy TextField loading in `capa_tracking_board`. Joined tables `lead_investigator`, `quality_owner`, `department` are never accessed, while large text fields are pulled across the wire without `.only(...)`.
  - *Fix*: Remove unused `select_related` and add `.only(...)` with only required header/metric fields.
- **PRF-I3**: `apps/quality/models/CapaManagement/CapaInvestigations.py:163-169`, `apps/quality/models/CapaManagement/CapaActions.py:110-116` — Missing compound tenant composite indexes for hot filter dimensions: `(tenant, action_type)` and `(tenant, department)`.
  - *Fix*: Add `models.Index(fields=["tenant", "action_type"], name="idx_qcap_ten_act_type")`, `models.Index(fields=["tenant", "department"], name="idx_qcap_ten_dept")` on `CapaInvestigation`, and `models.Index(fields=["tenant", "department"], name="idx_qact_ten_dept")` on `CapaAction`. Generate migration.

### Minor
- **PRF-M1**: `apps/quality/views/CapaManagement/CapaInvestigations.py:30-32` — Unused `select_related` joins (`lead_investigator`, `quality_owner`, `department`) in `capa_investigation_list`.
  - *Fix*: Clean up unused joins in `capa_investigation_list`.



