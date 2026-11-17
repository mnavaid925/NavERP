# Review Findings — Sub-module 12.3: Risk Management (ISO 14971 / FMEA) (Module 12 — Quality Management System, `quality`)

**Changeset reviewed**: `d0799fa5444471edddf0c0535571f03ef4e1373f...HEAD`
**Target App**: `apps/quality/` (Sub-module 12.3: `RiskManagement/`)
**Date**: 2026-11-17

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
- [ ] `CR-C1`: In `apps/quality/views/RiskManagement/FmeaMatrix.py` (lines 144-147, 259-267), in `fmea_matrix_export` and `risk_traceability_matrix_export`, omitting `plan` dumps all tenant assessments across all plans instead of matching HTML view's default selected plan. Also validate `plan_id` belongs to `request.tenant`.
- [ ] `CR-C2`: In `apps/quality/views/RiskManagement/RiskManagementPlans.py` (lines 177-186, 188-197) and `RiskReviewRecords.py` (lines 171-179), state-mutating and destructive actions (`plan_delete`, `plan_activate`, `review_approve`) should be gated with `@tenant_admin_required`.

### Important
- [ ] `CR-I1`: In `apps/core/navigation.py` (lines 3401-3407), `LIVE_LINKS["12.3"]` maps both "Hazard Identification & Analysis" and "Residual Risk Assessment" to `quality:risk_assessment_list`. Map "Residual Risk Assessment" to `quality:risk_traceability_matrix` to provide distinct live destinations for all feature bullets.
- [ ] `CR-I2`: In all four delete views (`RiskManagementPlans.py:182`, `RiskAssessments.py:182`, `RiskControlMeasures.py:171`, `RiskReviewRecords.py:164`), `obj.delete()` precedes `write_audit_log`, losing `obj.pk` (`object_id=None`). Must log audit record BEFORE calling `.delete()`.
- [ ] `CR-I3`: In `apps/quality/models/RiskManagement/RiskAssessments.py:280-291`, `save()` only computes residual scores if both severity and probability are set; if residual scores are cleared on update, stale residual RPN/level values persist. Add `else` branch to clear residual fields.
- [ ] `CR-I4`: In `apps/quality/views/RiskManagement/FmeaMatrix.py:62-68`, hardcoded raw CSS color strings in matrix cells.

### Minor
- [ ] `CR-M1`: In `apps/quality/admin.py`, search fields can be expanded: `RiskAssessmentAdmin.search_fields` add `plan__title`; `RiskControlMeasureAdmin.search_fields` add `risk_assessment__hazard_description`.
- [ ] `CR-M2`: In `apps/quality/models/RiskManagement/RiskManagementPlans.py`, add `assessments_count` and `unmitigated_risks_count` properties to model.
- [ ] `CR-M3`: In `apps/quality/views/RiskManagement/FmeaMatrix.py`, wrap all output fields in CSV exports with `csv_safe()`.

---

## Pass 2: Architecture Explorer (`explorer`)

### Critical
- [ ] `EX-C1`: `templates/quality/riskmanagement/risk_management_plan/detail.html:163` — template attempts to render `{{ plan.approved_signature.signer_printed_name }}`. However, `ElectronicSignatureRecord` defines this field as `signer_name`. Update to `plan.approved_signature.signer_name`.
- [ ] `EX-C2`: `templates/quality/riskmanagement/risk_assessment/list.html:78-129, 244, 254` — Contract Section 4.4 explicitly pins `hazard_category_choices` and `selected_cat` in view context, and view implements `hazard_category` filtering. However, the `hazard_category` filter dropdown was omitted from the filter form in `risk_assessment/list.html`, and omitted from pagination links. Add the `hazard_category` `<select>` filter dropdown and preserve `&hazard_category={{ selected_cat }}` in pagination links.

### Important
- [ ] `EX-I1`: `apps/quality/{models,forms,views,urls}/RiskManagement/` directories lack `__init__.py` files. Create `__init__.py` in each subpackage directory with appropriate entity re-exports.
- [ ] `EX-I2`: `apps/quality/models/RiskManagement/RiskAssessments.py:77, 83`, `RiskReviewRecords.py:30` specify badge class `"badge-purple"`. `static/css/theme.css` does not define `.badge-purple`. Replace with allowed theme class (`badge-info` or `badge-slate`).
- [ ] `EX-I3`: `apps/core/navigation.py:3401-3407` — in `LIVE_LINKS["12.3"]`, both "Hazard Identification & Analysis" and "Residual Risk Assessment" point to `quality:risk_assessment_list`. Update "Residual Risk Assessment" to point to `quality:risk_traceability_matrix`.
- [ ] `EX-I4`: `apps/quality/views/RiskManagement/FmeaMatrix.py:143-154, 258-271` — in `fmea_matrix_export` and `risk_traceability_matrix_export`, when `plan` param is omitted, views export all assessments across all plans instead of defaulting to `plans.first()`. Align export default with HTML view.
- [ ] `EX-I5`: `apps/quality/models/RiskManagement/RiskAssessments.py:280-291` — `save()` calculates residual RPN/level only when residual severity & probability are present; if cleared, stale calculations persist. Add `else` branch in `save()` to reset residual metrics.
- [ ] `EX-I6`: `apps/quality/views/RiskManagement/RiskManagementPlans.py:182`, `RiskAssessments.py:182`, `RiskControlMeasures.py:171`, `RiskReviewRecords.py:164` — `obj.delete()` called before `write_audit_log`, losing `obj.pk`. Call `write_audit_log` before `obj.delete()`.

### Minor
- [ ] `EX-M1`: `apps/quality/views/RiskManagement/RiskManagementPlans.py:97` — `RiskControlMeasure` is imported locally inside the view function. Move import to module top-level.
- [ ] `EX-M2`: `apps/quality/models/RiskManagement/RiskManagementPlans.py:130` — add `@property def assessments_count(self)` and `@property def unmitigated_risks_count(self)` to model.
- [ ] `EX-M3`: `apps/quality/admin.py:199, 217, 235` — add `plan__title` to `RiskAssessmentAdmin` & `RiskReviewRecordAdmin` search fields, and `risk_assessment__hazard_description` to `RiskControlMeasureAdmin` search fields.
- [ ] `EX-M4`: `apps/quality/views/RiskManagement/FmeaMatrix.py:62, 65, 68` — view generates raw inline CSS class strings in Python dict. Replace with semantic zone classes or template mapping.

---

## Pass 3: Frontend / UI / UX / Template Reviewer (`frontend-reviewer`)

### Critical
- [ ] `FR-C1`: `templates/quality/riskmanagement/risk_management_plan/detail.html:163` — `plan.approved_signature.signer_printed_name` attribute mismatch (actual field is `signer_name`). Update to `plan.approved_signature.signer_name`.

### Important
- [ ] `FR-I1`: `apps/quality/models/RiskManagement/RiskAssessments.py:77, 83`, `RiskReviewRecords.py:30` and templates specify non-existent `badge-purple`. Replace with `badge-info` or `badge-slate`.
- [ ] `FR-I2`: `templates/quality/riskmanagement/risk_assessment/list.html:78-129, 244, 254` — missing `hazard_category` filter `<select>` UI, missing from Clear Filters check, and missing from pagination links.
- [ ] `FR-I3`: `templates/quality/riskmanagement/fmea_matrix.html:248`, `risk_traceability_matrix.html:219` — non-existent `btn-xs` class used in table actions. Replace with `btn-sm`.
- [ ] `FR-I4`: Multiple list & detail templates have icon-only buttons missing `aria-label` for screen reader accessibility (WCAG 2.1 AA 4.1.2). Add matching `aria-label` attributes.

### Minor
- [ ] `FR-M1`: `templates/quality/riskmanagement/fmea_matrix.html:40`, `risk_traceability_matrix.html:40` — plan `<select onchange="this.form.submit()">` needs `<button type="submit" class="sr-only">Submit</button>` for keyboard accessibility.
- [ ] `FR-M2`: Multiple detail templates use unqualified `col-span-2` in detail grids. Change to `sm:col-span-2` for responsive mobile layout.
- [ ] `FR-M3`: Inconsistent arbitrary opacity utilities (`bg-white/70`, `bg-slate-50/50`, `bg-red-50/30`) in matrix templates. Replace with standard classes.

---

## Pass 4: Performance & Database Optimization Reviewer (`performance-reviewer`)

### Critical
- [ ] `PR-C1`: `apps/quality/views/RiskManagement/RiskManagementPlans.py:93-114` & `detail.html:219, 314` — 8 sequential COUNT round-trips on plan detail page (6 in view, 2 in template via `.count`). Batch assessment counts into a single `.aggregate()` call, batch control measure counts into `.aggregate()`, and replace `.count` in template with length or aggregated stats.

### Important
- [ ] `PR-I1`: `apps/quality/views/RiskManagement/{RiskManagementPlans,RiskAssessments,RiskControlMeasures,RiskReviewRecords}.py` — sequential unbatched KPI queries across all 4 list views (16 sequential queries). Replace with `.aggregate(Count("id", filter=Q(...)))`.
- [ ] `PR-I2`: `apps/quality/views/RiskManagement/FmeaMatrix.py:29-33, 117, 203-207, 238` — redundant standalone DB queries on already-evaluated querysets (`assessments.count()`) and duplicate `plans.exists()` followed by `plans.first()`. Use `len(assessments)` and direct `plans.first()`.
- [ ] `PR-I3`: `templates/quality/riskmanagement/risk_assessment/detail.html:213` — `{{ control_measures.count }}` issues redundant `SELECT COUNT(*)` query right before iteration. Replace with `{{ control_measures|length }}`.
- [ ] `PR-I4`: `apps/quality/views/RiskManagement/FmeaMatrix.py:290-293` — `controls.exists()` in export loop bypasses prefetch cache. Use `controls = list(a.control_measures.all())` and check `if controls:`.
- [ ] `PR-I5`: `apps/quality/models/RiskManagement/RiskAssessments.py:234-240` — missing compound index for hazard category filtering. Add `models.Index(fields=["tenant", "hazard_category"], name="idx_qrsk_ten_hazard_cat")` (<= 30 chars).

### Minor
- [ ] `PR-M1`: `apps/quality/views/RiskManagement/{RiskAssessments,RiskControlMeasures,RiskReviewRecords,FmeaMatrix}.py` — heavy `TextField` over-fetching in plan dropdown querysets. Add `.only("id", "number", "title", "matrix_dimension")`.
- [ ] `PR-M2`: `apps/quality/views/RiskManagement/RiskManagementPlans.py:84-91` — optimize `risk_management_plan_detail` prefetching.



