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
