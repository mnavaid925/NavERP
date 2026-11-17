# Review Findings — Sub-module 12.3: Risk Management (ISO 14971 / FMEA) (Module 12 — Quality Management System, `quality`)

**Changeset reviewed**: `d0799fa5444471edddf0c0535571f03ef4e1373f...HEAD`
**Target App**: `apps/quality/` (Sub-module 12.3: `RiskManagement/`) and `templates/quality/riskmanagement/`
**Date**: 2026-11-17

All six review passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) have concluded strictly serially. Below is the deduplicated, consolidated, and prioritized action register for Phase 5 (`code-fixer`).

---

## Consolidated Action Register

### Critical Findings

- [x] **C1**: `templates/quality/riskmanagement/risk_management_plan/detail.html:163` — Attribute name mismatch on electronic signature (`plan.approved_signature.signer_printed_name` vs `signer_name`). `ElectronicSignatureRecord` defines `signer_name`. Django template silently renders blank string.
  - *Fix*: Update line 163 to reference `{{ plan.approved_signature.signer_name }}`.
  - *Status*: [x] fixed — 501ea122 fix(quality): use signer_name for electronic signature on plan detail

- [x] **C2**: `templates/quality/riskmanagement/risk_assessment/list.html:78-129, 244, 254` — Missing `hazard_category` filter `<select>` UI and pagination link dropping filter. Contract Section 4.4 explicitly pins `hazard_category_choices` and `selected_cat`. View implements filtering, but template omits the dropdown, omits `selected_cat` in Clear Filters check, and drops param on pagination.
  - *Fix*: Add `<select id="category-filter" name="hazard_category" class="form-select">` with options to filter grid, include in Clear Filters check, and append `{% if selected_cat %}&hazard_category={{ selected_cat }}{% endif %}` to previous/next pagination links.
  - *Status*: [x] fixed — 405229de fix(quality): add hazard_category filter dropdown and preserve in pagination

- [x] **C3**: `apps/quality/views/RiskManagement/RiskManagementPlans.py:93-114` & `detail.html:219, 314` — Severe query explosion on plan detail page (8 sequential `COUNT(*)` database round-trips: 6 in view, 2 in template via `.count`).
  - *Fix*: Batch assessment KPI counts into single `.aggregate()`, batch control measure counts into single `.aggregate()`, and replace `{{ assessments.count }}` / `{{ reviews.count }}` in template with `{{ stats.total_assessments }}` / `{{ reviews|length }}`.
  - *Status*: [x] fixed — 1d7b0819 fix(quality): batch kpis, guard edits, audit before delete, and add tenant admin checks to plans; 4d8507e8 fix(quality): optimize count queries and responsive layout on plan detail

- [x] **C4**: `apps/quality/views/RiskManagement/FmeaMatrix.py:144-154, 259-271` — FMEA matrix and Risk Traceability matrix CSV exports dump all tenant records across all plans when `plan` param is omitted, diverging from HTML view which defaults to `plans.first()`. Furthermore, arbitrary `plan` ID inputs are not validated against `request.tenant` via `quality_object`.
  - *Fix*: Validate `plan` parameter with `quality_object(request, RiskManagementPlan, int(selected_plan_id))` when provided (returning 404 if invalid/cross-tenant). If `plan` is omitted, default `selected_plan` to `plans.first()` matching the HTML view.
  - *Status*: [x] fixed — 7ea64aa0 fix(quality): validate export plan id, default to first plan, and optimize query evaluation

- [x] **C5**: `apps/quality/views/RiskManagement/RiskManagementPlans.py:177, 188, 199`, `RiskAssessments.py:176`, `RiskControlMeasures.py:165`, `RiskReviewRecords.py:158, 170` — Destructive and milestone lifecycle actions (`plan_delete`, `plan_activate`, `plan_archive`, `risk_assessment_delete`, `risk_control_measure_delete`, `risk_review_record_delete`, `risk_review_record_approve`) lack `@tenant_admin_required`.
  - *Fix*: Import and apply `@tenant_admin_required` decorator from `apps.core.decorators` to all 7 destructive and lifecycle action endpoints.
  - *Status*: [x] fixed — 1d7b0819, 7a31ce65, 91817c56, 6370eb74 (applied @tenant_admin_required across all 7 endpoints)

---

### Important Findings

- [x] **I1**: `apps/core/navigation.py:3401-3407` — In `LIVE_LINKS["12.3"]`, both "Hazard Identification & Analysis" and "Residual Risk Assessment" point to `quality:risk_assessment_list`.
  - *Fix*: Map "Residual Risk Assessment" to `quality:risk_traceability_matrix` to provide distinct live destinations for all 5 feature bullets.
  - *Status*: [x] fixed — 842be014 fix(quality): route residual risk assessment live link to risk traceability matrix

- [x] **I2**: `apps/quality/views/RiskManagement/RiskManagementPlans.py:182`, `RiskAssessments.py:182`, `RiskControlMeasures.py:171`, `RiskReviewRecords.py:164` — All four delete views call `obj.delete()` before `write_audit_log`, resetting `obj.pk = None` and recording `object_id=None` in the audit trail.
  - *Fix*: Call `write_audit_log(request.user, obj, "delete", tenant=request.tenant)` BEFORE calling `obj.delete()`.
  - *Status*: [x] fixed — 1d7b0819, 7a31ce65, 91817c56, 6370eb74 (called write_audit_log before delete across all views)

- [x] **I3**: `apps/quality/models/RiskManagement/RiskAssessments.py:280-291` — `RiskAssessment.save()` only calculates residual metrics when both severity and probability are present. If an existing record has residual metrics cleared on update, stale `residual_rpn` and `residual_risk_level` persist in DB.
  - *Fix*: Add `else` branch in `save()` when residual severity/probability are absent: set `self.residual_rpn = None`, `self.residual_risk_level = ""`, `self.residual_risk_acceptable = False`.
  - *Status*: [x] fixed — a03ddd36 fix(quality): clear residual metrics on unset, enforce safety gates, and add category index

- [x] **I4**: `apps/quality/models/RiskManagement/`, `apps/quality/forms/RiskManagement/`, `apps/quality/views/RiskManagement/`, `apps/quality/urls/RiskManagement/` — Subpackage directories lack `__init__.py` files.
  - *Fix*: Create standard `__init__.py` in each directory re-exporting entities according to backend package conventions.
  - *Status*: [x] fixed — 13e12d78, c8b5d511, 2a4b2ca5, 44b32f7c (added __init__.py with re-exports across all 4 subpackages)

- [x] **I5**: `apps/quality/models/RiskManagement/RiskAssessments.py:77, 83`, `RiskReviewRecords.py:30` — Model choice dictionaries and templates reference non-existent CSS class `"badge-purple"`. `theme.css` only defines `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`.
  - *Fix*: Replace `"badge-purple"` with `"badge-info"` or `"badge-slate"`.
  - *Status*: [x] fixed — a03ddd36, bcfd23f0 fix(quality): replace non-existent badge-purple with badge-info on review type

- [x] **I6**: `templates/quality/riskmanagement/fmea_matrix.html:248`, `risk_traceability_matrix.html:219` — Non-existent CSS class `btn-xs` used in action buttons.
  - *Fix*: Replace `btn-xs` with standard `theme.css` class `btn-sm`.
  - *Status*: [x] fixed — c59b9ddf, 144d6dc6 (replaced btn-xs with btn-sm on matrix action buttons)

- [x] **I7**: Icon-only action buttons across list & detail templates lack `aria-label` for screen reader accessibility (WCAG 2.1 AA 4.1.2).
  - *Fix*: Add matching `aria-label` attributes to all icon-only action links/buttons.
  - *Status*: [x] fixed — 405229de, 4d8507e8, 3338a8f6, 6406cd01, a4a39dcd, d6cab9e1 (added aria-label to all icon buttons)

- [x] **I8**: `apps/quality/views/RiskManagement/{RiskManagementPlans,RiskAssessments,RiskControlMeasures,RiskReviewRecords}.py` — Sequential unbatched KPI queries across all 4 list views (16 sequential round-trips).
  - *Fix*: Replace each list view's 4 sequential `.count()` queries with a single `.aggregate(Count("id", filter=Q(...)))`.
  - *Status*: [x] fixed — 1d7b0819, 7a31ce65, 91817c56, 6370eb74 (batched KPI queries with single .aggregate() call)

- [x] **I9**: `apps/quality/views/RiskManagement/FmeaMatrix.py:29-33, 117, 203-207, 238` — Standalone DB queries fired on already-evaluated querysets (`assessments.count()`) and redundant `plans.exists()` check right before `plans.first()`.
  - *Fix*: Use `len(assessments)` / `len(traceability_rows)` and direct `if not selected_plan: selected_plan = plans.first()`.
  - *Status*: [x] fixed — 7ea64aa0 fix(quality): validate export plan id, default to first plan, and optimize query evaluation

- [x] **I10**: `templates/quality/riskmanagement/risk_assessment/detail.html:213` — `{{ control_measures.count }}` issues redundant `SELECT COUNT(*)` query right before iteration.
  - *Fix*: Replace with `{{ control_measures|length }}`.
  - *Status*: [x] fixed — 3338a8f6 fix(quality): optimize count query, add aria-labels, and responsive grid on assessment detail

- [x] **I11**: `apps/quality/views/RiskManagement/FmeaMatrix.py:290-293` — In `risk_traceability_matrix_export`, `controls.exists()` can bypass prefetch cache and trigger N+1 queries.
  - *Fix*: Use `controls = list(a.control_measures.all())` and check `if controls:`.
  - *Status*: [x] fixed — 7ea64aa0 fix(quality): validate export plan id, default to first plan, and optimize query evaluation

- [x] **I12**: `apps/quality/models/RiskManagement/RiskAssessments.py:234-240` — Missing compound index on `(tenant, hazard_category)` for fast category filtering.
  - *Fix*: Add `models.Index(fields=["tenant", "hazard_category"], name="idx_qrsk_ten_hazard_cat")` to `RiskAssessment.Meta.indexes`.
  - *Status*: [x] fixed — a03ddd36 (model index added), 3b77434e feat(quality): add idx_qrsk_ten_hazard_cat compound index on riskassessment

- [x] **I13**: `apps/quality/forms/RiskManagement/RiskReviewRecords.py:27` — Mass assignment vulnerability on `status`: form includes `"status"`, allowing users to set `status="approved"` directly via form POST and bypass approval workflow.
  - *Fix*: Restrict `status` choices in `RiskReviewRecordForm.__init__` to `[("draft", "Draft"), ("under_review", "Under Review")]`, or exclude `"status"` from `Meta.fields` (defaulting to `"draft"`).
  - *Status*: [x] fixed — 7c21ec3f fix(quality): restrict status choices on review record form to prevent mass assignment

- [x] **I14**: `apps/quality/forms/RiskManagement/RiskControlMeasures.py:28, 29` — Mass assignment on verification flags: `implementation_verified` and `effectiveness_verified` can be checked without verification evidence notes or test protocol.
  - *Fix*: In `RiskControlMeasureForm.clean()`, require `verification_notes` or `design_verification` if either verification flag is checked.
  - *Status*: [x] fixed — 219ebcaa fix(quality): enforce verification notes on verified flags and validate cross-project consistency

- [x] **I15**: `apps/quality/forms/RiskManagement/RiskAssessments.py:30` & `RiskAssessments.py:280-291` — Safety gate bypass: arbitrary acceptance of residual risks in the Unacceptable zone (Red, $S \times P \ge 15$), and lack of Clinical Benefit-Risk justification requirement for ALARP zone.
  - *Fix*: In `RiskAssessmentForm.clean()`, reject `residual_risk_acceptable=True` if calculated residual level is `"unacceptable"`, and require `benefit_risk_justification` if in ALARP zone. In `RiskAssessment.save()`, enforce `self.residual_risk_acceptable = False` if `self.residual_risk_level == "unacceptable"`.
  - *Status*: [x] fixed — a03ddd36 (save safety gate), a1ca6337 fix(quality): enforce safety gates rejecting unacceptable residual risk and requiring alarp bra justification

- [x] **I16**: `apps/quality/views/RiskManagement/RiskManagementPlans.py:154-164`, `RiskReviewRecords.py:135-145` — Modification of electronically signed or active plans and approved review records without revoking signature or creating new revision breaks 21 CFR Part 11 integrity.
  - *Fix*: In `risk_management_plan_edit` and `risk_review_record_edit`, guard against editing active/signed plans or approved review records, redirecting with a user error message.
  - *Status*: [x] fixed — 1d7b0819, 6370eb74 (guarded plan and review edit views)

---

### Minor Findings

- [x] **M1**: `apps/quality/admin.py:199, 217, 235` — Search fields in `admin.py` can be expanded for related foreign keys.
  - *Fix*: Add `plan__title` to `RiskAssessmentAdmin` & `RiskReviewRecordAdmin.search_fields`, and `risk_assessment__hazard_description` to `RiskControlMeasureAdmin.search_fields`.
  - *Status*: [x] fixed — b56da105 fix(quality): expand admin search fields with related plan and hazard descriptions

- [x] **M2**: `apps/quality/models/RiskManagement/RiskManagementPlans.py:130` — Model lacks helper properties `assessments_count` and `unmitigated_risks_count`.
  - *Fix*: Add `@property def assessments_count(self)` and `@property def unmitigated_risks_count(self)` to `RiskManagementPlan`.
  - *Status*: [x] fixed — 65a4ec9a feat(quality): add assessments_count and unmitigated_risks_count helper properties to plan model

- [x] **M3**: `apps/quality/views/RiskManagement/RiskManagementPlans.py:97` — `RiskControlMeasure` is imported locally inside the view function.
  - *Fix*: Move import to module top-level.
  - *Status*: [x] fixed — 1d7b0819 (moved RiskControlMeasure import to top-level)

- [x] **M4**: `apps/quality/views/RiskManagement/FmeaMatrix.py:62-68` — View generates raw inline CSS class strings in cell dict.
  - *Fix*: Map cell colors via clean CSS classes or semantic zone mapping.
  - *Status*: [x] fixed — 7ea64aa0 (mapped cell colors via ZONE_CLASSES dictionary)

- [x] **M5**: `templates/quality/riskmanagement/fmea_matrix.html:40`, `risk_traceability_matrix.html:40` — Plan `<select onchange="this.form.submit()">` needs a visually hidden submit button for keyboard accessibility.
  - *Fix*: Add `<button type="submit" class="sr-only">Submit</button>`.
  - *Status*: [x] fixed — c59b9ddf, 144d6dc6 (added sr-only submit button to plan select forms)

- [x] **M6**: Detail templates use unqualified `col-span-2` in detail grids.
  - *Fix*: Change `col-span-2` to `sm:col-span-2` for responsive mobile layout.
  - *Status*: [x] fixed — 4d8507e8, 3338a8f6, 1f18ba3f, 6c08a68a (updated col-span-2 to sm:col-span-2 across all 4 detail templates)

- [x] **M7**: Matrix templates use arbitrary opacity modifiers (`bg-white/70`, `bg-slate-50/50`, `bg-red-50/30`).
  - *Fix*: Replace with standard solid background classes (`bg-white`, `bg-slate-50`, `bg-red-50`).
  - *Status*: [x] fixed — c59b9ddf, 144d6dc6 (replaced opacity modifiers with solid background classes)

- [x] **M8**: Heavy `TextField` over-fetching in plan dropdown querysets across list and matrix views.
  - *Fix*: Add `.only("id", "number", "title", "matrix_dimension")` to plan querysets.
  - *Status*: [x] fixed — 7ea64aa0, 7a31ce65, 91817c56, 6370eb74 (applied .only(...) to plan querysets)

- [x] **M9**: In all 5 view modules, `csv_safe(value)` checks `text.startswith(...)` without stripping leading whitespace, allowing formula bypass (e.g. ` =1+1`).
  - *Fix*: Update `csv_safe` to check `text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%"))` and wrap all export values with `csv_safe`.
  - *Status*: [x] fixed — 1d7b0819, 7ea64aa0, 7a31ce65, 91817c56, 6370eb74 (hardened csv_safe and wrapped all export values)

- [x] **M10**: `apps/quality/forms/RiskManagement/RiskControlMeasures.py:67-74` — Missing cross-project consistency validation between `risk_assessment.plan.design_project` and `design_input.project`.
  - *Fix*: In `RiskControlMeasureForm.clean()`, check if `risk_assessment.plan.design_project_id` matches `design_input.project_id` when both are set.
  - *Status*: [x] fixed — 219ebcaa fix(quality): enforce verification notes on verified flags and validate cross-project consistency

- [x] **M11**: `apps/quality/views/RiskManagement/RiskManagementPlans.py:84-91` — Detail view prefetching optimization.
  - *Fix*: Use `prefetch_related` on plan assessments and reviews.
  - *Status*: [x] fixed — 1d7b0819 (optimized plan detail querysets)

---

## Raw Review Passes Record

### Pass 1: Code Reviewer (`code-reviewer`)
- `CR-C1`: In `FmeaMatrix.py` exports, handle omitted `plan` and validate `plan_id`.
- `CR-C2`: Gate state-mutating actions with `@tenant_admin_required`.
- `CR-I1`: Map "Residual Risk Assessment" in `navigation.py` to `risk_traceability_matrix`.
- `CR-I2`: Call `write_audit_log` before `.delete()`.
- `CR-I3`: Clear residual fields in `RiskAssessment.save()` when residual inputs are unset.
- `CR-I4`: Replace raw CSS colors in matrix cells.
- `CR-M1`: Expand admin search fields.
- `CR-M2`: Add helper properties to `RiskManagementPlan`.
- `CR-M3`: Wrap export values in `csv_safe`.

### Pass 2: Architecture Explorer (`explorer`)
- `EX-C1`: Plan detail e-signature attribute mismatch (`signer_printed_name` vs `signer_name`).
- `EX-C2`: Missing `hazard_category` filter in assessment list.
- `EX-I1`: Missing `__init__.py` files in `RiskManagement/` subpackage folders.
- `EX-I2`: Undefined `badge-purple` in model CSS maps.
- `EX-I3`: Duplicate `navigation.py` link for Residual Risk Assessment.
- `EX-I4`: Export default plan alignment with HTML view.
- `EX-I5`: Clear residual risk fields on update.
- `EX-I6`: Audit log `object_id=None` on delete.
- `EX-M1`: Local import in `RiskManagementPlans.py`.
- `EX-M2`: Add model count helper properties.
- `EX-M3`: Admin search field coverage.
- `EX-M4`: Presentation classes in view.

### Pass 3: Frontend / UI / UX / Template Reviewer (`frontend-reviewer`)
- `FR-C1`: `signer_printed_name` vs `signer_name` mismatch.
- `FR-I1`: Invalid badge `badge-purple`.
- `FR-I2`: Missing `hazard_category` filter dropdown and pagination param loss.
- `FR-I3`: Undefined `btn-xs` button class.
- `FR-I4`: Icon-only buttons missing `aria-label`.
- `FR-M1`: Plan select keyboard accessibility.
- `FR-M2`: Unqualified `col-span-2` on mobile.
- `FR-M3`: Arbitrary opacity utilities in matrices.

### Pass 4: Performance & Database Optimization Reviewer (`performance-reviewer`)
- `PR-C1`: Severe query explosion on plan detail (8 sequential counts).
- `PR-I1`: 16 unbatched sequential KPI counts across list views.
- `PR-I2`: Redundant DB queries on evaluated querysets.
- `PR-I3`: Redundant `.count()` in assessment detail template.
- `PR-I4`: Potential prefetch bypass via `.exists()` in export loop.
- `PR-I5`: Missing compound index for hazard category.
- `PR-M1`: TextField over-fetching in dropdown querysets.
- `PR-M2`: Detail view prefetch optimization.

### Pass 5: QA Smoke Tester — Report-Only Mode (`qa-smoke-tester`)
- `QA-I1`: Silent blank rendering of e-signature signer name.
- `QA-I2`: Missing `hazard_category` filter UI & pagination parameter drop.
- `QA-I3`: Undefined CSS class `badge-purple` rendered in DOM.
- `QA-M1`: Default plan filtering discrepancy between HTML and CSV export.

### Pass 6: Security Reviewer (`security-reviewer`)
- `SR-I1`: Missing `@tenant_admin_required` on destructive and lifecycle actions.
- `SR-I2`: Lost audit log `object_id` on deletion.
- `SR-I3`: Mass assignment bypass of review approval in `RiskReviewRecordForm`.
- `SR-I4`: Mass assignment bypass of risk control verification in `RiskControlMeasureForm`.
- `SR-I5`: Safety gate bypass: arbitrary acceptance of unacceptable residual risks.
- `SR-I6`: Electronic signature / post-approval tampering guard on active/signed plans and approved reviews.
- `SR-M1`: CSV formula injection bypass via leading whitespace.
- `SR-M2`: Missing cross-project consistency validation in `RiskControlMeasureForm`.
- `SR-M3`: Silent invalid plan ID handling in FMEA exports.
