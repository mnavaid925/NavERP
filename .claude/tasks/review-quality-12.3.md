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
